import tkinter as tk
from tkinter import ttk
import pandas as pd
import os

csv_path = os.path.join("data", "processed_movies.csv")
df = pd.read_csv(csv_path)

def recommend_movies():
    genre = genre_var.get()
    try:
        duration = float(duration_entry.get())
        rating = float(rating_entry.get())
    except ValueError:
        result_text.set("Durasi dan rating harus berupa angka.")
        return

    df['score'] = df.apply(lambda row: (
        abs(row['runtime'] - duration) * 0.5 +
        abs(row['vote_average'] - rating) * 1.5 +
        (0 if row['main_genre'] == genre else 2)
    ), axis=1)

    recommendations = df.sort_values('score').head(5)

    result = ""
    for _, row in recommendations.iterrows():
        result += f"{row['title']} ({row['main_genre']}) - Durasi: {row['runtime']}m, Rating: {row['vote_average']}\n"
    result_text.set(result)

root = tk.Tk()
root.title("CBR Rekomendasi Film")
root.geometry("500x400")

font_label = ("Poppins", 11)
font_entry = ("Poppins", 11)
font_result = ("Poppins", 10)

genre_var = tk.StringVar()
duration_entry = tk.Entry(root, font=font_entry)
rating_entry = tk.Entry(root, font=font_entry)
result_text = tk.StringVar()

tk.Label(root, text="Pilih Genre:", font=font_label).grid(row=0, column=0, sticky="w", padx=10, pady=5)
genre_menu = ttk.Combobox(root, textvariable=genre_var, values=sorted(df['main_genre'].unique().tolist()), font=font_entry)
genre_menu.grid(row=0, column=1, padx=10, pady=5)

tk.Label(root, text="Durasi (menit):", font=font_label).grid(row=1, column=0, sticky="w", padx=10, pady=5)
duration_entry.grid(row=1, column=1, padx=10, pady=5)

tk.Label(root, text="Rating Minimum:", font=font_label).grid(row=2, column=0, sticky="w", padx=10, pady=5)
rating_entry.grid(row=2, column=1, padx=10, pady=5)

tk.Button(root, text="Rekomendasikan", command=recommend_movies, font=font_label, bg="#4CAF50", fg="white").grid(
    row=3, column=0, columnspan=2, pady=15
)

tk.Label(root, textvariable=result_text, justify="left", wraplength=450, font=font_result, anchor="w").grid(
    row=4, column=0, columnspan=2, padx=10, sticky="w"
)

root.mainloop()
