import re
import sys
import io

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from database import DatabaseHandler

# Initialize the Cave Johnson Database Interface
db = DatabaseHandler()

# The raw data payload from the "Test Subject" (You)
# Structure: Category -> List of Games
raw_data = {
    "Automation": [
        "Scrap Mechanic", "Factorio", "Satisfactory", "Astroneer", "Foundry", 
        "Dyson Sphere Program", "Outpost: Infinity Siege", "Techtonica", "Timberborn", 
        "Surviving Mars: Reloaded", "Ostranauts", "ΔV: Rings of Saturn", "Tin Can", 
        "The Crust", "Block Factory", "Upload Labs", "The Farmer Was Replaced", 
        "Time to Morp", "Sixty Four", "Hydroneer", "Nova Lands"
    ],
    "4 Player Party": [
        "Deep Rock Galactic", "The Horde Wants You Dead", "Warhammer: Vermintide", 
        "Borderlands", "Helldivers", "Jump Ship", "Void Crew (6)", "Schedule 1", 
        "Stormworks", "Left 4 Dead", "Dying Light", "Ready or Not", "World War Z", 
        "Aliens: Fireteam Elite (3)", "Fallout 76", "Phasmophobia", "Content Warning", 
        "Far Far West", "Light No Fire", "Den of Wolves", "Generation Zero (4)"
    ],
    "Free/Party": [
        "Open Front", "Geoguesser", "Jackbox", "Stick Fight", "Overcooked", 
        "Deadlock", "Warzone", "Fortnite", "Roblox", "Agar.io", "Heavenly Bodies"
    ],
    "Simulation/Adventure": [
        "RoadCraft", "Star Trucker", "Hardspace: Shipbreaker", "Pacific Drive", 
        "Juno: New Origins", "Kerbal Space Program", "Space Engineers", "Space Haven", 
        "The Alters", "Ixion", "Elite Dangerous", "Tank Rat", "Tank Head", "RoboCop", 
        "Journey to the Savage Planet", "Revenge of the Savage Planet", 
        "Vampire: The Masquerade - Bloodlines 2", "Hitman", "Storm Chasers", 
        "Aniimo", "Prince of Persia 2"
    ],
    "Survival Hill": [
        "Enshrouded", "V Rising", "Grounded", "Grounded 2", "Forever Skies (3)", 
        "Minecraft", "Bellwright (shit?)", "Valheim", "Icarus", "ARK", "Rust (shit?)", 
        "Misery", "7 Days to Die", "Project Zomboid", "Core Keeper", "Terraria", 
        "Necesse", "Stardew Valley", "Animal Crossing", "Vein (shit)", "Green Hell", 
        "Subnautica", "Voidtrain", "Raft", "Sons of the Forest", "No Man's Sky", 
        "Palworld", "Runescape: Dragonwilds", "Abiotic Factor", "Saleblazers", 
        "Nightingale", "Conan Exiles"
    ],
    "VR Vibes": [
        "Beat Saber", "Gorn", "Underdogs", "Half-Life: Alyx", 
        "Clone Drone in the Hyperdome", "Thrill of the Fight", "Racket: Nx", 
        "Electronauts", "Walkabout Mini Golf", "Space Pirate Trainer", "Ancient Dungeon", 
        "Carly and the Reaperman", "Rumble", "Zenith: Nexus", "VRChat", "Pistol Whip", 
        "Walking Dead: Saints & Sinners", "Forewarned", "Gorilla Tag", "Population: One", 
        "Zero Caliber", "Pavlov", "Contractors", "Into the Radius", "Into the Radius 2", 
        "BattleGroupVR", "Hot Dogs, Horseshoes & Hand Grenades", "VTOL VR", 
        "Blade & Sorcery", "Hubris", "Ghost Town", "Deadpool VR", "Arken Age", 
        "Laser Dance", "Reach", "Cave Cave", "Sail", "Quantum Void"
    ]
}

# Specific Cave Johnson Notes for key titles
cave_notes = {
    "Factorio": "The factory must grow. If you stop for a bathroom break, you're fired.",
    "Satisfactory": "Inefficient. Needs more conveyor belts. And less nature.",
    "Deep Rock Galactic": "Management approves of the mining, but not the dancing.",
    "Kerbal Space Program": "More boosters! If it doesn't explode, you aren't doing science.",
    "Portal 2": "Mandatory testing protocol.",
    "Phasmophobia": "If a ghost kills you, fill out the injury waiver forms in triplicate.",
    "Subnautica": "Note: Ocean planet contains zero lemons. Do not attempt to make lemonade.",
    "Helldivers": "Spreading Managed Democracy is cheaper than therapy.",
    "Hardspace: Shipbreaker": "You have a debt to pay, sparky. Get to work.",
    "Bellwright": "User annotation indicates quality concerns. Proceed with caution.",
    "Rust": "Tetanus shots required before entry.",
    "Vein": "User annotation indicates this simulation may be... sub-optimal."
}

def clean_entry(entry):
    """
    Parses entries like 'Void Crew (6)' or 'Bellwright (shit?)'
    Returns: (cleaned_title, max_players, extra_note)
    """
    max_players = 4 # Default standard
    note = None
    
    # Check for player counts like (6) or (3)
    count_match = re.search(r'\((\d+)\s*(?:max)?\)', entry, re.IGNORECASE)
    if count_match:
        max_players = int(count_match.group(1))
        entry = re.sub(r'\(\d+\s*(?:max)?\)', '', entry).strip()

    # Check for quality notes like (shit?)
    quality_match = re.search(r'\((shit\??)\)', entry, re.IGNORECASE)
    if quality_match:
        note = "User Note: Potential quality issues detected."
        entry = re.sub(r'\(shit\??\)', '', entry).strip()

    return entry, max_players, note

def seed_database():
    print("🔬 Aperture Science Database Importer Initialized.")
    print("--------------------------------------------------")
    
    # Ensure tables exist
    db.setup_tables()
    
    added_count = 0
    tag_count = 0
    
    # We iterate through the dictionary
    for category, games in raw_data.items():
        for raw_game in games:
            title, max_players, dynamic_note = clean_entry(raw_game)
            
            # Determine Cave Note
            final_note = cave_notes.get(title, dynamic_note)
            if not final_note:
                final_note = "Testing protocol awaiting data."

            # Add Game (Returns ID or -1 if exists)
            # Defaulting min_players to 1 for simplicity
            game_id = db.add_game(
                title=title,
                added_by=0, # 0 = System/Cave Johnson
                category=category,
                min_players=1,
                max_players=max_players,
                status='seen',
                notes=final_note,
                store_link=None
            )
            
            # Handle Tags
            if game_id == -1:
                # If game exists, we might need to fetch its ID to add a new tag
                # (Skipping complex logic for this script, assuming clean DB)
                print(f"⚠️  Duplicate detected: {title}. Skipping...")
            else:
                added_count += 1
                
                # Default Tag based on Category
                tags = [category]
                
                # Extra Inference Tags
                if "VR" in category or "VR" in title:
                    tags.append("VR")
                if "Party" in category:
                    tags.append("Co-op")
                if "Survival" in category:
                    tags.append("Survival")
                if "Simulation" in category:
                    tags.append("Simulation")
                
                db.add_tags(game_id, tags)
                tag_count += len(tags)
                print(f"✅ Imported: {title}")

    print("--------------------------------------------------")
    print(f"🎉 SUCCESS! {added_count} simulations added to the roster.")
    print(f"🏷️  {tag_count} classification tags applied.")
    print("Cave Johnson here—we're done. Get back to work.")

if __name__ == "__main__":
    seed_database()