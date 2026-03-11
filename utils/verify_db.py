import asyncio
from database import DatabaseHandler

async def verify():
    db = DatabaseHandler()

    print("--- Testing RAG Logic ---")
    print("1. Searching for 'Co-op' with 4 players:")
    recommendations = await db.recommend_games(min_players=4, tag="Co-op")
    print(recommendations)

    print("\n2. Searching for 'Survival':")
    recommendations_survival = await db.recommend_games(tag="Survival")
    print(recommendations_survival)

    print("\n--- Testing Retrieval of New Fields ---")
    async with db.get_connection() as conn:
        async with conn.execute("SELECT title, external_rating, ideal_players, release_date FROM games LIMIT 3") as cursor:
            rows = await cursor.fetchall()
            
    for row in rows:
        print(f"Title: {row[0]}, Rating: {row[1]}, Ideal: {row[2]}, Date: {row[3]}")

if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except Exception as e:
        import traceback
        with open("verify_error.txt", "w") as f:
            traceback.print_exc(file=f)
