from database import DatabaseHandler

db = DatabaseHandler()

print("--- Testing RAG Logic ---")
print("1. Searching for 'Co-op' with 4 players:")
recommendations = db.recommend_games(min_players=4, tag="Co-op")
print(recommendations)

print("\n2. Searching for 'Survival':")
recommendations_survival = db.recommend_games(tag="Survival")
print(recommendations_survival)

print("\n--- Testing Retrieval of New Fields ---")
conn = db.get_connection()
c = conn.cursor()
c.execute("SELECT title, external_rating, ideal_players, release_date FROM games LIMIT 3")
rows = c.fetchall()
conn.close()
for row in rows:
    print(f"Title: {row[0]}, Rating: {row[1]}, Ideal: {row[2]}, Date: {row[3]}")
