from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import os
import logging
from datetime import datetime
import json
import urllib.parse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

csv_path = os.path.join("data", "processed_movies.csv")
case_base_path = os.path.join("data", "case_base.json")
feedback_path = os.path.join("data", "movie_feedback.json")

def load_case_base():
    if os.path.exists(case_base_path):
        try:
            with open(case_base_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return []
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading case base: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading case base: {e}")
            return []
    return []

def save_case_base(case_base):
    try:
        with open(case_base_path, 'w', encoding='utf-8') as f:
            json.dump(case_base, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving case base: {e}")

def calculate_similarity(movie, user_preferences):
    similarity_score = 0

    if user_preferences.get('genre') and movie.get('main_genre') == user_preferences.get('genre'):
        similarity_score += 0.4

    try:
        target_rating = float(user_preferences.get('rating', 0))
        rating_diff = abs((movie.get('vote_average') or 0) - target_rating)
        similarity_score += 0.3 * (1 - (rating_diff / 10))
    except (ValueError, TypeError):
        pass

    user_duration_str = user_preferences.get('duration')
    target_duration = 0
    if user_duration_str == '60':
        target_duration = 75
    elif user_duration_str == '90':
        target_duration = 105
    elif user_duration_str == '120':
        target_duration = 135
    elif user_duration_str == '150':
        target_duration = 165
    elif user_duration_str == '180':
        target_duration = 200

    if target_duration > 0 and movie.get('runtime') is not None:
        duration_diff = abs((movie.get('runtime') or 0) - target_duration)
        similarity_score += 0.2 * (1 - (duration_diff / 200))

    user_year_range = user_preferences.get('year_range')
    if user_year_range:
        try:
            if '>=' in user_year_range:
                target_year = int(user_year_range.split('>=')[1])
                year_diff = max(0, target_year - (movie.get('year') or 0))
            else:
                start_year, end_year = map(int, user_year_range.split('-'))
                target_year = (start_year + end_year) / 2
                year_diff = abs((movie.get('year') or 0) - target_year)
            similarity_score += 0.1 * (1 - (year_diff / 50))
        except (ValueError, TypeError, IndexError):
            pass

    return similarity_score

def adapt_recommendation(movie, user_preferences):
    return movie

def revise_recommendation(recommendation, user_feedback, all_movies_df):
    if user_feedback.get('rating', 0) < 4:
        genre = recommendation.get('main_genre')
        if genre:
            alternative_movies = all_movies_df[
                (all_movies_df.get('main_genre') == genre) &
                (all_movies_df.get('vote_average', 0) > recommendation.get('vote_average', 0))
            ].sort_values('vote_average', ascending=False)

            if not alternative_movies.empty:
                logger.info(f"Revising recommendation: Found {len(alternative_movies)} alternatives in genre {genre}.")
                return alternative_movies.iloc[0].to_dict()
            else:
                 logger.info(f"Revising recommendation: No higher-rated alternatives found in genre {genre}.")

    logger.info("Revising recommendation: No revision needed or no suitable alternative found.")
    return recommendation

def load_feedback():
    if os.path.exists(feedback_path):
        try:
            with open(feedback_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading feedback: {e}")
            return []
    return []

def save_feedback(feedback_data):
    try:
        with open(feedback_path, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")

def get_feedback_for_movie(movie_title):
    feedback_data = load_feedback()
    movie_feedback = [
        feedback for feedback in feedback_data
        if feedback.get('movie_title') == movie_title
    ]
    movie_feedback.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return movie_feedback

try:
    logger.info(f"Attempting to load CSV from {csv_path}")
    df = pd.read_csv(csv_path)

    required_cols = ['main_genre', 'vote_average', 'runtime', 'year', 'title', 'overview', 'genres', 'id']
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"Column '{col}' not found in CSV. Adding with default/empty values.")
            if col in ['year', 'runtime', 'vote_average', 'id']:
                df[col] = 0
            elif col == 'genres':
                df[col] = '[]'
            else:
                df[col] = ''

    if 'release_date' in df.columns and 'year' in df.columns and (df['year'] == 0).all():
         try:
             df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year.fillna(0).astype(int)
             logger.info("Extracted 'year' from 'release_date' column")
         except Exception as e:
              logger.error(f"Error extracting year from release_date: {str(e)}")
              df['year'] = 0

    df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)
    logger.info("Successfully ensured 'year' column is integer")

    for col in ['runtime', 'vote_average', 'id']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        logger.info(f"Successfully ensured '{col}' column is numeric")

    for col in ['title', 'main_genre', 'overview']:
        df[col] = df[col].astype(str).fillna('')
        logger.info(f"Successfully ensured '{col}' column is string")

    if 'main_genre' not in df.columns and 'genres' in df.columns:
        try:
            df['main_genre'] = df['genres'].apply(lambda x: json.loads(x)[0]['name'] if isinstance(x, str) and json.loads(x) else 'N/A')
            logger.info("Extracted 'main_genre' from 'genres' column")
        except Exception as e:
            logger.error(f"Error extracting main_genre from genres: {str(e)}")
            df['main_genre'] = 'N/A'

    min_year = df['year'].min() if not df.empty and 'year' in df.columns else 2010
    max_year = df['year'].max() if not df.empty and 'year' in df.columns else 2024
    logger.info(f"Year range: {min_year} to {max_year}")

except FileNotFoundError:
    logger.error(f"CSV file not found at {csv_path}")
    df = pd.DataFrame()
    min_year = 2010
    max_year = 2024
except Exception as e:
    logger.error(f"Unexpected error loading CSV: {str(e)}")
    df = pd.DataFrame()
    min_year = 2010
    max_year = 2024

all_movies_df = df

@app.route('/', methods=['GET', 'POST'])
def index():
    genres = sorted(all_movies_df['main_genre'].dropna().unique().tolist()) if not all_movies_df.empty else []
    recommendations = []
    error = ""
    request_form = request.form
    page = 1

    user_preferences = {
        'genre': request_form.get('genre'),
        'duration': request_form.get('duration'),
        'rating': request_form.get('rating'),
        'year_range': request_form.get('year_range')
    }

    if request.method == 'POST':
        logger.info("Handling POST request for /")
        if all_movies_df.empty:
            logger.warning("No data available for recommendations on POST")
            error = "Data film tidak tersedia. Silakan coba lagi nanti."
        else:
            try:
                page = int(request_form.get('page', 1))
                logger.info(f"Received POST values - {user_preferences}, Page: {page}")

                try:
                    filtered_df = all_movies_df.copy()

                    if user_preferences.get('genre'):
                        filtered_df = filtered_df[filtered_df['main_genre'] == user_preferences['genre']].copy()

                    if user_preferences.get('year_range'):
                        yr = user_preferences['year_range']
                        try:
                            if '>=' in yr:
                                year_threshold = int(yr.split('>=')[1])
                                filtered_df = filtered_df[filtered_df['year'] >= year_threshold].copy()
                            else:
                                start_y, end_y = map(int, yr.split('-'))
                                filtered_df = filtered_df[(filtered_df['year'] >= start_y) & (filtered_df['year'] <= end_y)].copy()
                        except Exception:
                            logger.warning(f"Invalid year range format: {yr}")

                    if user_preferences.get('rating'):
                        rating_str = user_preferences['rating'].strip()
                        try:
                            if '-' in rating_str:
                                low, high = map(float, rating_str.split('-'))
                                filtered_df = filtered_df[(filtered_df['vote_average'] >= low) & (filtered_df['vote_average'] <= high)].copy()
                            else:
                                rating_val = float(rating_str)
                                high_bound = min(rating_val + 1, 10.1)
                                filtered_df = filtered_df[(filtered_df['vote_average'] >= rating_val) & (filtered_df['vote_average'] < high_bound)].copy()
                        except Exception:
                            logger.warning(f"Invalid rating value: {rating_str}")

                    if user_preferences.get('duration'):
                         duration_map = {
                             '60': (0, 90),
                             '90': (90, 120),
                             '120': (120, 150),
                             '150': (150, 180),
                             '180': (180, float('inf'))
                         }
                         duration_range = duration_map.get(user_preferences['duration'])
                         if duration_range:
                             low_dur, high_dur = duration_range
                             filtered_df = filtered_df[(filtered_df['runtime'] >= low_dur) & (filtered_df['runtime'] < high_dur)].copy()

                    filtered_df['similarity_score'] = filtered_df.apply(
                        lambda x: calculate_similarity(x.to_dict(), user_preferences),
                        axis=1
                    )

                    filtered_df = filtered_df.sort_values(by=['vote_average', 'similarity_score'], ascending=[False, False])

                    movies_per_page = 6
                    start_idx = (page - 1) * movies_per_page
                    end_idx = start_idx + movies_per_page
                    recommendations = filtered_df.iloc[start_idx:end_idx].to_dict(orient='records')

                except Exception as e:
                    logger.error(f"Error during recommendation process: {str(e)}")
                    error = "Terjadi kesalahan saat memproses rekomendasi film." + str(e)

            except Exception as e:
                logger.error(f"Unexpected error in POST handling: {str(e)}")
                error = "Terjadi kesalahan yang tidak terduga saat memproses permintaan." + str(e)

    if request.method == 'POST' and not recommendations and not error:
        logger.info("No recommendations found, rendering not_found.html")
        return render_template('not_found.html')
    else:
        return render_template(
            'index.html',
            genres=genres,
            min_year=min_year,
            max_year=max_year,
            recommendations=recommendations,
            error=error,
            request_form=user_preferences,
            total_movies=len(filtered_df) if 'filtered_df' in locals() else len(all_movies_df),
            current_page=page,
            movies=all_movies_df.to_dict(orient='records')
        )

@app.route('/movie/<path:movie_title>/feedback', methods=['GET'])
def movie_feedback_page(movie_title):
    decoded_title = urllib.parse.unquote(movie_title)
    logger.info(f"Accessing feedback page for movie: {decoded_title}")

    movie_data = all_movies_df[all_movies_df['title'] == decoded_title].iloc[0].to_dict() if not all_movies_df[all_movies_df['title'] == decoded_title].empty else None

    if not movie_data:
        return "Film tidak ditemukan", 404

    existing_feedback = get_feedback_for_movie(decoded_title)

    return render_template(
        'feedback.html',
        movie=movie_data,
        feedback_list=existing_feedback
    )

@app.route('/get_feedback/<path:movie_title>', methods=['GET'])
def get_feedback(movie_title):
    decoded_title = urllib.parse.unquote(movie_title)
    feedback = get_feedback_for_movie(decoded_title)
    return jsonify({'feedback': feedback})

@app.route('/submit_movie_feedback', methods=['POST'])
def submit_movie_feedback():
    try:
        movie_title = request.form.get('movie_title')
        user_rating = request.form.get('rating')
        user_comment = request.form.get('comment')

        if not movie_title or not user_rating:
            return jsonify({'success': False, 'message': 'Missing movie title or rating.'}), 400

        movie_data = all_movies_df[all_movies_df['title'] == movie_title].iloc[0].to_dict() if not all_movies_df[all_movies_df['title'] == movie_title].empty else None

        if not movie_data:
            return jsonify({'success': False, 'message': f'Movie with title "{movie_title}" not found.'}), 404

        feedback_data = {
            'movie_title': movie_title,
            'rating': int(user_rating),
            'comment': user_comment if user_comment else '',
            'timestamp': datetime.now().isoformat(),
            'movie_details': {
                'year': movie_data.get('year'),
                'genre': movie_data.get('main_genre'),
                'runtime': movie_data.get('runtime'),
                'vote_average': movie_data.get('vote_average')
            }
        }

        all_feedback = load_feedback()
        all_feedback.append(feedback_data)
        save_feedback(all_feedback)

        logger.info(f"Feedback submitted for movie: {movie_title}")

        encoded_title = urllib.parse.quote(movie_title)
        return redirect(url_for('movie_feedback_page', movie_title=encoded_title))

    except ValueError as e:
        logger.error(f"Invalid input data: {str(e)}")
        return jsonify({'success': False, 'message': 'Invalid input data provided.'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in submit_movie_feedback: {str(e)}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
