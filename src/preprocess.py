import pandas as pd
import ast
import os

# Baca file CSV dari folder data
input_path = os.path.join("data", "movies_metadata.csv")
output_path = os.path.join("data", "processed_movies.csv")

# Membaca dataset
df = pd.read_csv(input_path, low_memory=False)

# Hanya kolom yang dibutuhkan
df = df[['title', 'genres', 'runtime', 'vote_average', 'imdb_id', 'release_date']]

# Hapus baris kosong pada kolom yang relevan
df.dropna(subset=['genres', 'runtime', 'vote_average', 'imdb_id', 'release_date'], inplace=True)

# Ubah string genres ke list dictionary dan ambil genre utama
def extract_main_genre(genres_str):
    try:
        genres = ast.literal_eval(genres_str)
        if isinstance(genres, list) and genres:
            return genres[0]['name']
    except:
        return None

df['main_genre'] = df['genres'].apply(extract_main_genre)

# Hapus genre yang tidak bisa diambil dan film tanpa imdb_id/release_date
df.dropna(subset=['main_genre', 'imdb_id', 'release_date'], inplace=True)

# Pastikan imdb_id adalah string yang valid (dimulai dengan 'tt')
df = df[df['imdb_id'].astype(str).str.startswith('tt')]

# Ubah release_date ke format datetime dan ekstrak tahun
df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
df['year'] = df['release_date'].dt.year

# Hapus baris yang gagal diubah ke datetime atau tahunnya kosong
df.dropna(subset=['release_date', 'year'], inplace=True)

# Simpan hasilnya
df[['title', 'main_genre', 'runtime', 'vote_average', 'imdb_id', 'release_date', 'year']].to_csv(output_path, index=False)
print("Preprocessing selesai. File disimpan di:", output_path)
