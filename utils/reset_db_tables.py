import sqlite3
import os

db_path = 'data/doodlab.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        print("Dropping games...")
        c.execute("DROP TABLE IF EXISTS games")
        print("Dropping ratings...")
        c.execute("DROP TABLE IF EXISTS game_ratings")
        print("Dropping tags...")
        c.execute("DROP TABLE IF EXISTS game_tags")
        conn.commit()
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Database file not found.")
