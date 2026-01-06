import sys
import os
import io

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.database import DatabaseHandler

def verify_list():
    print("🔬 LIST SIMPLIFICATION VERIFICATION 🔬")
    print("---------------------------------------")
    
    db = DatabaseHandler()
    
    # Test: Find games for exactly 4 players
    print("\n[TEST] Searching for games supporting 4 players...")
    games = db.get_game_library(player_count=4)
    print(f"     Found {len(games)} games.")
    
    # Verify one result
    if games:
        sample = games[0]
        print(f"     Sample: {sample['title']} (Min: {sample['min_players']}, Max: {sample['max_players']})")
        if sample['min_players'] <= 4 <= sample['max_players']:
             print("     ✅ Correctly filtered.")
        else:
             print("     ❌ Incorrect filter!")
    else:
        print("     ⚠️ No games found (might be expected if DB is empty/no match).")

if __name__ == "__main__":
    verify_list()
