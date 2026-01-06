import sqlite3
import sys
import io
from database import DatabaseHandler

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Initialize the Cave Johnson Database Interface
db = DatabaseHandler()

# HARDCODED MANIFEST OF MANDATORY FUN
# Fields: Title, Category, Min Players, Max Players, Store Link (Steam/Epic), Cave's Note
seed_manifest = [
    # --- AUTOMATION SECTOR ---
    {"title": "Factorio", "tags": ["Automation", "Isometric", "Co-op", "Space"], "min": 1, "max": 65535, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Full Release", "link": "https://store.steampowered.com/app/427520/Factorio/", "note": "The factory must grow. Bathroom breaks are unauthorized."},
    {"title": "Satisfactory", "tags": ["Automation", "First Person", "Base Building", "Co-op", "Space"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/526870/Satisfactory/", "note": "Inefficient. Too much nature. Pave over it."},
    {"title": "Scrap Mechanic", "tags": ["Automation", "Third Person", "Co-op", "Physics"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2016", "state": "Early Access", "link": "https://store.steampowered.com/app/387990/Scrap_Mechanic/", "note": "If the vehicle explodes, you built it right."},
    {"title": "Astroneer", "tags": ["Automation", "Third Person", "Base Building", "Co-op", "Survival", "Space"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Full Release", "link": "https://store.steampowered.com/app/361420/ASTRONEER/", "note": "Suffocation risks are within acceptable tolerances."},
    {"title": "Dyson Sphere Program", "tags": ["Automation", "Third Person", "Isometric", "Space"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2021", "state": "Early Access", "link": "https://store.steampowered.com/app/1366540/Dyson_Sphere_Program/", "note": "Finally, someone thinking big. Harness the star!"},
    {"title": "Timberborn", "tags": ["Automation", "City Builder", "Survival"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2021", "state": "Early Access", "link": "https://store.steampowered.com/app/1062090/Timberborn/", "note": "Beavers doing engineering? Better than some of my actual staff."},
    {"title": "Techtonica", "tags": ["Automation", "First Person", "Co-op", "Voxel"], "min": 1, "max": 4, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Early Access", "link": "https://store.steampowered.com/app/1457320/Techtonica/", "note": "Underground manufacturing. Good for hiding the... accidents."},
    {"title": "Hydroneer", "tags": ["Automation", "First Person", "Co-op", "Physics", "Base Building"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "https://store.steampowered.com/app/1106840/Hydroneer/", "note": "Mining with water pressure. Clever."},
    {"title": "Outpost: Infinity Siege", "tags": ["Automation", "First Person", "Tower Defense", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mixed", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/1566690/Outpost_Infinity_Siege/", "note": "Turrets on a moving base. Now we're talking."},
    {"title": "Foundry", "tags": ["Automation", "First Person", "Voxel", "Mecha", "Base Building", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2024", "state": "Early Access", "link": "https://store.steampowered.com/app/983870/FOUNDRY/", "note": "Voxel-based efficiency training."},
    {"title": "The Crust", "tags": ["Automation", "City Builder", "Space"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2024", "state": "Early Access", "link": "https://store.steampowered.com/app/1465470/The_Crust/", "note": "Lunar colonization protocol."},
    {"title": "Nova Lands", "tags": ["Automation", "Isometric", "Base Building"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Full Release", "link": "https://store.steampowered.com/app/1501610/Nova_Lands/", "note": "Optimization of alien resources."},
    {"title": "Surviving Mars: Reloaded", "tags": ["Automation", "City Builder", "Survival", "Strategy", "Space"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": "Assumption: 'Surviving Mars'"},
    {"title": "Ostranauts", "tags": ["Automation", "Isometric", "Space", "Survival"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Early Access", "link": "", "note": ""},
    {"title": "ΔV: Rings of Saturn", "tags": ["Automation", "Isometric", "Space", "Physics"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2019", "state": "Full Release", "link": "", "note": ""},
    {"title": "Tin Can", "tags": ["Automation", "First Person", "Survival", "Management"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2022", "state": "Full Release", "link": "", "note": ""},
    {"title": "Block Factory", "tags": ["Automation", "Voxel", "Puzzle"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/2827680/Block_Factory/", "note": ""},
    {"title": "Upload Labs", "tags": ["Automation", "Puzzle", "Free"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/3606890/Upload_Labs/", "note": ""},
    {"title": "The Farmer Was Replaced", "tags": ["Automation"], "min": 1, "max": 1, "ideal": 1, "status": "wishlisted", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "", "note": "Programming automation"},
    {"title": "Time to Morp", "tags": ["Automation", "Co-op", "Creature Collector"], "min": 1, "max": 4, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Early Access", "link": "", "note": ""},
    {"title": "Sixty Four", "tags": ["Automation", "Incremental"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mixed", "date": "2024", "state": "Full Release", "link": "", "note": "Clicker/Automation"},

    # --- 4 PLAYER PARTY SECTOR ---
    {"title": "Deep Rock Galactic", "tags": ["Classic", "Co-op", "Shooter", "Horde", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Full Release", "link": "https://store.steampowered.com/app/548430/Deep_Rock_Galactic/", "note": "Management approves of the mining quotas. Less dancing, more digging."},
    {"title": "Left 4 Dead 2", "tags": ["Classic", "Co-op", "Shooter", "Zombie", "Horde", "PVP", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2009", "state": "Full Release", "link": "https://store.steampowered.com/app/550/Left_4_Dead_2/", "note": "Zombie apocalypses are great for cardio."},
    {"title": "Helldivers 2", "tags": ["Shooter", "Wave", "Co-op", "Space", "Comedy", "Classic", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/553850/HELLDIVERS_2/", "note": "Spreading Managed Democracy is cheaper than therapy."},
    {"title": "Warhammer: Vermintide 2", "tags": ["Melee", "Horde", "Co-op", "Tactical", "Fantasy", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "https://store.steampowered.com/app/552500/Warhammer_Vermintide_2/", "note": "Rat extermination duty. Don't complain."},
    {"title": "Phasmophobia", "tags": ["Co-op", "Horror", "Investigation", "Social", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Early Access", "link": "https://store.steampowered.com/app/739630/Phasmophobia/", "note": "If a ghost kills you, fill out the injury waiver forms in triplicate."},
    {"title": "Lethal Company", "tags": ["Co-op", "Horror", "Comedy", "Low-Fi", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2023", "state": "Early Access", "link": "https://store.steampowered.com/app/1966720/Lethal_Company/", "note": "The perfect corporate structure. You are expendable assets."},
    {"title": "Content Warning", "tags": ["Co-op", "Comedy", "Horror", "Social", "Party"], "min": 2, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/2881650/Content_Warning/", "note": "Film the monster eating your friend. For science. And views."},
    {"title": "Void Crew", "tags": ["Co-op", "Space", "Simulation", "Action", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Early Access", "link": "https://store.steampowered.com/app/1063420/Void_Crew/", "note": "In space, no one can hear you scream at your pilot."},
    {"title": "Ready or Not", "tags": ["Co-op", "Tactical", "First Person", "Shooter", "Party"], "min": 1, "max": 4, "ideal": 5, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Full Release", "link": "https://store.steampowered.com/app/1144200/Ready_or_Not/", "note": "Tactical breach protocol. Try not to shoot the civilians this time."},
    {"title": "Payday 2", "tags": ["Co-op", "Shooter", "Tactical", "Action", "Classic", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2013", "state": "Full Release", "link": "https://store.steampowered.com/app/218620/PAYDAY_2/", "note": "Wealth redistribution experiment."},
    {"title": "GTFO", "tags": ["Co-op", "Tactical", "Hardcore", "Stealth", "Horror", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Full Release", "link": "https://store.steampowered.com/app/493520/GTFO/", "note": "Work together or die together. I prefer the latter, less paperwork."},
    {"title": "The Horde Wants You Dead", "tags": ["Co-op", "Horde", "Action", "Isometric", "Party"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mixed", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/3552820/The_Horde_Wants_You_Dead/", "note": "Hard to find data"},
    {"title": "Borderlands", "tags": ["Co-op", "RPG", "Comedy", "Classic", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2009", "state": "Full Release", "link": "https://store.steampowered.com/app/729040/Borderlands_Game_of_the_Year_Enhanced/", "note": "Series"},
    {"title": "Jump Space", "tags": ["Co-op", "Space", "First Person", "Shooter", "Exploration", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Early Access", "link": "https://store.steampowered.com/app/1757300/Jump_Space/", "note": ""},
    {"title": "Schedule 1", "tags": ["Co-op", "Action", "Management", "Automation", "Simulation", "Party"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2025", "state": "Early Access", "link": "https://store.steampowered.com/app/3164500/Schedule_I/", "note": ""},
    {"title": "Stormworks", "tags": ["Co-op", "Physics", "Building", "Simulation", "Party"], "min": 1, "max": 16, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2020", "state": "Full Release", "link": "", "note": "Build & Rescue"},
    {"title": "Dying Light", "tags": ["Co-op", "Zombie", "Shooter", "Action", "Horror", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2015", "state": "Full Release", "link": "", "note": ""},
    {"title": "World War Z", "tags": ["Co-op", "Zombie", "Horde", "Third Person", "Shooter", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Full Release", "link": "", "note": ""},
    {"title": "Aliens: Fireteam Elite", "tags": ["Shooter", "Action", "Third Person", "Horde", "Space", "Party"], "min": 1, "max": 3, "ideal": 3, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Full Release", "link": "", "note": "Raw note: (3)"},
    {"title": "Fallout 76", "tags": ["Co-op", "Survival", "RPG", "Post-Apocalyptic", "Shooter", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},
    {"title": "Far Far West", "tags": ["Co-op", "Shooter", "Action", "Western", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "N/A", "date": "2026", "state": "Early Access", "link": "", "note": ""},
    {"title": "Light No Fire", "tags": ["Co-op", "Fantasy", "Exploration", "Survival", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": "Unreleased"},
    {"title": "Den of Wolves", "tags": ["Co-op", "Tactical", "Shooter", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": "Unreleased"},
    {"title": "Generation Zero", "tags": ["Co-op", "Mecha", "Shooter", "Survival", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2019", "state": "Full Release", "link": "", "note": "Raw note: (4)"},

    # --- SIMULATION / ADVENTURE ---
    {"title": "Kerbal Space Program", "tags": ["Simulation", "Space", "Physics", "Construction"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2015", "state": "Full Release", "link": "https://store.steampowered.com/app/220200/Kerbal_Space_Program/", "note": "More boosters! If it doesn't explode, you aren't trying hard enough."},
    {"title": "Pacific Drive", "tags": ["Simulation", "Driving", "Survival", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/1458140/Pacific_Drive/", "note": "Station wagons and radiation. My kind of road trip."},
    {"title": "Hardspace: Shipbreaker", "tags": ["Simulation", "Space", "Physics", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2022", "state": "Full Release", "link": "https://store.steampowered.com/app/1161580/Hardspace_Shipbreaker/", "note": "You have a debt to pay, sparky. Get to work."},
    {"title": "Elite Dangerous", "tags": ["Simulation", "Space", "Flight", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2014", "state": "Full Release", "link": "https://store.steampowered.com/app/359320/Elite_Dangerous/", "note": "Space trucking simulator. Watch out for Thargoids."},
    {"title": "SnowRunner", "tags": ["Simulation", "Driving", "Physics", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "https://store.steampowered.com/app/1465360/SnowRunner/", "note": "Getting stuck in mud is apparently fun for you people."},
    {"title": "RoadCraft", "tags": ["Simulation", "Driving", "Construction"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/2104890/RoadCraft/", "note": "Restoration logistics"},
    {"title": "Star Trucker", "tags": ["Simulation", "Driving", "First Person", "Space"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2024", "state": "Full Release", "link": "", "note": "Space trucking with a CB radio vibe."},
    {"title": "Juno: New Origins", "tags": ["Simulation", "Space", "Physics", "Construction"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Full Release", "link": "", "note": "Previously SimpleRockets 2"},
    {"title": "Space Engineers", "tags": ["Simulation", "Space", "Base Building", "Physics", "Co-op"], "min": 1, "max": 16, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Full Release", "link": "", "note": ""},
    {"title": "Space Haven", "tags": ["Simulation", "Space", "Base Building", "Isometric", "Survival"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Early Access", "link": "", "note": ""},
    {"title": "The Alters", "tags": ["Simulation", "Space", "Survival", "Base Building"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/1601570/The_Alters/", "note": ""},
    {"title": "Ixion", "tags": ["Simulation", "Space", "City Builder", "Survival", "Strategy"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2022", "state": "Full Release", "link": "", "note": ""},
    {"title": "Tank Rat", "tags": ["Simulation", "Action", "Shooter", "Mecha"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": ""},
    {"title": "Tank Head", "tags": ["Simulation", "Action", "Mecha", "Shooter"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mostly Positive", "date": "2025", "state": "Full Release", "link": "https://store.epicgames.com/en-US/p/tankhead-2f3b51", "note": ""},
    {"title": "RoboCop", "tags": ["Simulation", "First Person", "Shooter", "Action", "Adventure", "RPG"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Full Release", "link": "", "note": "RoboCop: Rogue City"},
    {"title": "Journey to the Savage Planet", "tags": ["Adventure", "Exploration", "Comedy", "First Person", "Co-op"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "", "note": ""},
    {"title": "Revenge of the Savage Planet", "tags": ["Adventure", "Exploration", "Comedy", "First Person", "Co-op"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/2787320/Revenge_of_the_Savage_Planet/", "note": "Send P-Body"},
    {"title": "Vampire: The Masquerade - BL2", "tags": ["Simulation", "RPG", "Vampire", "Action"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mixed", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/532790/Vampire_The_Masquerade__Bloodlines_2/", "note": "Needs further testing"},
    {"title": "Hitman", "tags": ["Simulation", "Stealth", "Puzzle", "Third Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Full Release", "link": "", "note": "Hitman 3 (WoA)"},
    {"title": "Storm Chasers", "tags": ["Simulation", "Driving", "Co-op", "Survival"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mixed", "date": "2016", "state": "Early Access", "link": "", "note": ""},
    {"title": "Aniimo", "tags": ["Simulation", "Creature Collector", "Mounts"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": ""},
    {"title": "Prince of Persia 2", "tags": ["Adventure", "Platformer", "Action"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "", "note": "Assuming 'The Lost Crown' or Classic"},
    {"title": "Farming Simulator 2025", "tags": ["Simulation", "Farming", "Mounts", "Co-op"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/2300320/Farming_Simulator_25/", "note": ""},
    {"title": "Red Dead Redemption 2", "tags": ["Adventure", "Action", "RPG", "Co-op", "Western"], "min": 1, "max": 60, "ideal": 5, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},

    # --- SURVIVAL HILL ---
    {"title": "Valheim", "tags": ["Survival", "Voxel", "Melee", "Fantasy", "Base Building", "Co-op", "Farming"], "min": 1, "max": 10, "ideal": 5, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2021", "state": "Early Access", "link": "https://store.steampowered.com/app/892970/Valheim/", "note": "The bees are happy. Are you? Back to work."},
    {"title": "Project Zomboid", "tags": ["Survival", "Zombie", "Hardcore", "Isometric", "RPG", "Base Building", "Co-op", "Farming"], "min": 1, "max": 32, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2013", "state": "Early Access", "link": "https://store.steampowered.com/app/108600/Project_Zomboid/", "note": "This is how you died. Try to do it with some dignity."},
    {"title": "7 Days to Die", "tags": ["Survival", "Zombie", "Horde", "Voxel", "First Person", "Base Building", "Co-op", "Farming"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/251570/7_Days_to_Die/", "note": "Building forts out of garbage. Classic."},
    {"title": "Rust", "tags": ["Survival", "PVP", "Hardcore", "Base Building", "Co-op", "Farming"], "min": 1, "max": 100, "ideal": 8, "status": "Played", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "https://store.steampowered.com/app/252490/Rust/", "note": "Tetanus shots required before entry."},
    {"title": "Subnautica", "tags": ["Survival", "Exploration", "First Person", "Base Building", "Singleplayer", "Farming"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2018", "state": "Full Release", "link": "https://store.steampowered.com/app/264710/Subnautica/", "note": "Ocean planet contains zero lemons. Do not attempt to make lemonade."},
    {"title": "No Man's Sky", "tags": ["Survival", "Space", "Exploration", "Base Building", "Mobile Base", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2016", "state": "Full Release", "link": "https://store.steampowered.com/app/275850/No_Mans_Sky/", "note": "Infinite universe, and you're still just mining rocks."},
    {"title": "Enshrouded", "tags": ["Survival", "RPG", "Melee", "Voxel", "Fantasy", "Base Building", "Co-op", "Farming"], "min": 1, "max": 16, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Early Access", "link": "https://store.steampowered.com/app/1203620/Enshrouded/", "note": "Fog based construction. Acceptable."},
    {"title": "V Rising", "tags": ["Survival", "Vampire", "Melee", "Isometric", "Action", "Mounts", "Base Building", "PVP", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "", "note": "Clan size 4"},
    {"title": "Grounded", "tags": ["Survival", "Adventure", "First Person", "Melee", "Base Building", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2022", "state": "Full Release", "link": "", "note": "Miniature survival in a backyard."},
    {"title": "Grounded 2", "tags": ["Survival", "Co-op", "Creature Collector", "Melee", "Mounts", "Base Building", "Farming"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": "Likely not real yet"},
    {"title": "Forever Skies", "tags": ["Survival", "Post-Apocalyptic", "First Person", "Base Building", "Mobile Base", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Early Access", "link": "", "note": "Raw note: (3)?"},
    {"title": "Minecraft", "tags": ["Survival", "Sandbox", "Voxel", "Mounts", "Co-op", "Melee", "Mods", "Farming"], "min": 1, "max": 999, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2011", "state": "Full Release", "link": "", "note": ""},
    {"title": "Bellwright", "tags": ["Survival", "Fantasy", "Strategy", "Base Building", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 2, "status": "Played", "rating": "Mixed", "date": "2024", "state": "Early Access", "link": "", "note": "Raw note: (shit?)"},
    {"title": "Icarus", "tags": ["Survival", "Space", "Base Building", "Mounts", "First Person", "Co-op", "Farming"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2021", "state": "Full Release", "link": "", "note": ""},
    {"title": "ARK", "tags": ["Survival", "Base Building", "Mounts", "Co-op", "Farming"], "min": 1, "max": 70, "ideal": 10, "status": "Unknown", "rating": "Mixed", "date": "2023", "state": "Early Access", "link": "", "note": "ARK: Survival Ascended"},
    {"title": "Misery", "tags": ["Survival", "Hardcore", "Horror", "Mods"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2013", "state": "Full Release", "link": "", "note": "Likely the STALKER mod"},
    {"title": "Core Keeper", "tags": ["Survival", "Isometric", "Voxel", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "", "note": ""},
    {"title": "Terraria", "tags": ["Survival", "Sandbox", "Base Building", "Adventure", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2011", "state": "Full Release", "link": "", "note": ""},
    {"title": "Necesse", "tags": ["Survival", "Isometric", "Strategy", "Base Building", "Co-op", "Low-Fi"], "min": 1, "max": 10, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Early Access", "link": "", "note": ""},
    {"title": "Stardew Valley", "tags": ["Cozy", "Casual", "Farming", "RPG", "Low-Fi", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2016", "state": "Full Release", "link": "", "note": ""},
    {"title": "Animal Crossing", "tags": ["Cozy", "Casual"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "", "note": "Animal Crossing: NH"},
    {"title": "Vein", "tags": ["Survival", "Zombie", "Hardcore", "Simulation", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Played", "rating": "Very Positive", "date": "2021", "state": "Early Access", "link": "", "note": "Raw note: (shit)"},
    {"title": "Green Hell", "tags": ["Survival", "Hardcore", "First Person", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Full Release", "link": "", "note": ""},
    {"title": "Voidtrain", "tags": ["Survival", "Space", "Mobile Base", "First Person", "Base Building", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mostly Positive", "date": "2023", "state": "Early Access", "link": "", "note": ""},
    {"title": "Raft", "tags": ["Survival", "Base Building", "Mobile Base", "First Person", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2022", "state": "Full Release", "link": "", "note": ""},
    {"title": "Sons of the Forest", "tags": ["Survival", "Horror", "First Person", "Base Building", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Full Release", "link": "", "note": ""},
    {"title": "Palworld", "tags": ["Survival", "Creature Collector", "Base Building", "Co-op", "Farming"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Early Access", "link": "", "note": "Guild size larger"},
    {"title": "Runescape: Dragonwilds", "tags": ["Survival", "MMO", "Fantasy"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Early Access", "link": "https://store.steampowered.com/app/1374490/RuneScape_Dragonwilds/", "note": "Possible fan project?"},
    {"title": "Abiotic Factor", "tags": ["Survival", "Co-op", "First Person", "Base Building", "Low-Fi", "Farming"], "min": 1, "max": 6, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2024", "state": "Early Access", "link": "", "note": "Science-team survival."},
    {"title": "Saleblazers", "tags": ["Survival", "Management", "Fantasy", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Early Access", "link": "", "note": ""},
    {"title": "Nightingale", "tags": ["Survival", "Fantasy", "Melee", "Base Building", "Co-op", "Farming"], "min": 1, "max": 6, "ideal": 4, "status": "Unknown", "rating": "Mixed", "date": "2024", "state": "Early Access", "link": "", "note": ""},
    {"title": "Conan Exiles", "tags": ["Survival", "Fantasy", "PVP", "Base Building", "Mounts", "Co-op", "Farming"], "min": 1, "max": 40, "ideal": 10, "status": "Unknown", "rating": "Mostly Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},

    # --- VR VIBES ---
    {"title": "Beat Saber", "tags": ["VR", "Rhythm", "Fitness"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2019", "state": "Full Release", "link": "https://store.steampowered.com/app/620980/Beat_Saber/", "note": "Flailing around with laser swords. Watch the furniture."},
    {"title": "Half-Life: Alyx", "tags": ["VR", "First Person", "Shooter", "Adventure", "Horror"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Full Release", "link": "https://store.steampowered.com/app/546560/HalfLife_Alyx/", "note": "We do what we must because we can."},
    {"title": "VRChat", "tags": ["VR", "Social", "Free", "Creative"], "min": 1, "max": 40, "ideal": 10, "status": "Unknown", "rating": "Very Positive", "date": "2017", "state": "Early Access", "link": "https://store.steampowered.com/app/438100/VRChat/", "note": "I have seen the face of god, and it was a waifu avatar."},
    {"title": "Blade and Sorcery", "tags": ["VR", "Physics", "Melee", "Sandbox", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2024", "state": "Full Release", "link": "https://store.steampowered.com/app/629730/Blade_and_Sorcery/", "note": "Stress relief protocol engaged."},
    {"title": "Gorn", "tags": ["VR", "Melee", "Physics"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2019", "state": "Full Release", "link": "", "note": ""},
    {"title": "Underdogs", "tags": ["VR", "Mecha", "Roguelike", "Physics", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2024", "state": "Full Release", "link": "", "note": "Mech arena combat."},
    {"title": "Clone Drone in the Danger Zone", "tags": ["VR", "Melee", "Voxel", "Action", "Co-op"], "min": 1, "max": 4, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Full Release", "link": "", "note": "User note had 'Hyperdome'"},
    {"title": "Thrill of the Fight", "tags": ["VR", "Melee", "Fitness", "Simulation"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2016", "state": "Full Release", "link": "", "note": "Genuinely exhausting."},
    {"title": "Racket: Nx", "tags": ["VR", "Sports", "Arcade", "Co-op"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},
    {"title": "Electronauts", "tags": ["VR", "Rhythm", "Creative", "Casual"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},
    {"title": "Walkabout Mini Golf", "tags": ["VR", "Sports", "Casual", "Co-op"], "min": 1, "max": 8, "ideal": 4, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Full Release", "link": "", "note": "Top tier social VR."},
    {"title": "Space Pirate Trainer", "tags": ["VR", "Arcade", "Pirate", "Shooter", "Wave"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2017", "state": "Full Release", "link": "", "note": ""},
    {"title": "Ancient Dungeon", "tags": ["VR", "Roguelike", "Adventure", "Voxel", "Co-op"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2021", "state": "Early Access", "link": "", "note": ""},
    {"title": "Carly and the Reaperman", "tags": ["VR", "Platformer", "Co-op"], "min": 2, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": "One person in VR, one on PC."},
    {"title": "Rumble", "tags": ["VR", "Fantasy", "Physics", "Multiplayer"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2022", "state": "Early Access", "link": "", "note": "Earthbending mechanics."},
    {"title": "Zenith: Nexus", "tags": ["VR", "MMO", "RPG", "Co-op"], "min": 1, "max": 100, "ideal": 4, "status": "Unknown", "rating": "Mixed", "date": "2022", "state": "Early Access", "link": "", "note": ""},
    {"title": "Pistol Whip", "tags": ["VR", "Rhythm", "Shooter", "Action"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2019", "state": "Full Release", "link": "", "note": "John Wick rhythm game."},
    {"title": "Walking Dead: Saints & Sinners", "tags": ["VR", "Horror", "Survival", "First Person", "Adventure"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "", "note": ""},
    {"title": "Forewarned", "tags": ["VR", "Horror", "Investigation", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Early Access", "link": "", "note": "Phasmophobia but Egyptian tombs."},
    {"title": "Gorilla Tag", "tags": ["VR", "Social", "Free"], "min": 1, "max": 10, "ideal": 6, "status": "Unknown", "rating": "Very Positive", "date": "2021", "state": "Early Access", "link": "", "note": ""},
    {"title": "Population: One", "tags": ["VR", "Battle Royale", "Shooter", "Co-op"], "min": 1, "max": 24, "ideal": 3, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "", "note": "Squad-based combat."},
    {"title": "Zero Caliber", "tags": ["VR", "First Person", "Shooter", "Co-op"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": ""},
    {"title": "Pavlov", "tags": ["VR", "First Person", "Shooter", "PVP"], "min": 1, "max": 24, "ideal": 10, "status": "Unknown", "rating": "Very Positive", "date": "2017", "state": "Full Release", "link": "", "note": ""},
    {"title": "Contractors", "tags": ["VR", "First Person", "Shooter", "Mods"], "min": 1, "max": 16, "ideal": 10, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "", "note": "Call of Duty vibe in VR."},
    {"title": "Into the Radius", "tags": ["VR", "Survival", "Horror", "Hardcore", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2020", "state": "Full Release", "link": "", "note": "STALKER-esque VR."},
    {"title": "Into the Radius 2", "tags": ["VR", "Survival", "Horror", "Co-op", "Hardcore"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2024", "state": "Early Access", "link": "", "note": ""},
    {"title": "BattleGroupVR", "tags": ["VR", "Strategy", "Space", "Co-op"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Very Positive", "date": "2023", "state": "Full Release", "link": "", "note": ""},
    {"title": "H3VR", "tags": ["VR", "Simulation", "Shooter", "Physics", "Sandbox"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2016", "state": "Early Access", "link": "", "note": "Hot Dogs, Horseshoes & Hand Grenades."},
    {"title": "VTOL VR", "tags": ["VR", "Simulation", "Flight", "Co-op"], "min": 1, "max": 8, "ideal": 2, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2020", "state": "Full Release", "link": "", "note": ""},
    {"title": "Hubris", "tags": ["VR", "Adventure", "Space", "First Person"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Mixed", "date": "2022", "state": "Full Release", "link": "", "note": ""},
    {"title": "Ghost Town", "tags": ["VR", "Horror", "Puzzle", "Adventure"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "N/A", "date": "2025", "state": "Early Access", "link": "", "note": ""},
    {"title": "Arken Age", "tags": ["VR", "Adventure", "Action", "RPG"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Full Release", "link": "https://store.steampowered.com/app/2274200/Arken_Age/", "note": ""},
    {"title": "Laser Dance", "tags": ["VR", "Fitness", "Puzzle"], "min": 1, "max": 1, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2025", "state": "Early Access", "link": "https://www.meta.com/experiences/laser-dance/7209598115800315/", "note": "Move through laser grids in your room."},
    {"title": "Sail", "tags": ["VR", "Pirate", "RPG", "Co-op"], "min": 1, "max": 4, "ideal": 3, "status": "Unknown", "rating": "Mixed", "date": "2022", "state": "Early Access", "link": "", "note": "Sea of Thieves VR style."},

    # --- FREE / PARTY SECTOR ---
    {"title": "Open Front", "tags": ["Tactical", "Browser", "Strategy", "PVP", "Free"], "min": 1, "max": 20, "ideal": 10, "status": "Unknown", "rating": "N/A", "date": "2024", "state": "Full Release", "link": "", "note": "Indie tactical shooter."},
    {"title": "Geoguessr", "tags": ["Browser", "Free"], "min": 1, "max": 100, "ideal": 1, "status": "Unknown", "rating": "Very Positive", "date": "2013", "state": "Full Release", "link": "https://www.geoguessr.com/", "note": "Knowing where a specific pole is in Romania is a life skill."},
    {"title": "Jackbox Party Packs", "tags": ["Casual", "Classic", "Party"], "min": 2, "max": 8, "ideal": 6, "status": "Unknown", "rating": "Very Positive", "date": "Various", "state": "Full Release", "link": "", "note": "Audience can join via phone. High potential for chaos."},
    {"title": "Stick Fight: The Game", "tags": ["Physics", "Melee", "PVP", "Classic", "Party"], "min": 2, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2017", "state": "Full Release", "link": "https://store.steampowered.com/app/674940/Stick_Fight_The_Game/", "note": "Simple, fast, and remarkably frustrating in a good way."},
    {"title": "Overcooked 2", "tags": ["Co-op", "Management", "Classic", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Very Positive", "date": "2018", "state": "Full Release", "link": "https://store.steampowered.com/app/728880/Overcooked_2/", "note": "A true test of any friendship or relationship."},
    {"title": "Deadlock", "tags": ["MOBA", "Shooter", "PVP", "Third Person", "Free", "Party"], "min": 6, "max": 12, "ideal": 6, "status": "Unknown", "rating": "N/A", "date": "TBA", "state": "Early Access", "link": "", "note": "Valve's hero-shooter MOBA hybrid."},
    {"title": "Warzone", "tags": ["Battle Royale", "First Person", "Shooter", "PVP", "Free", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "Mixed", "date": "2020", "state": "Full Release", "link": "", "note": "Standard high-intensity squad shooter."},
    {"title": "Fortnite", "tags": ["Battle Royale", "Building", "Sandbox", "Free", "Social", "Party"], "min": 1, "max": 4, "ideal": 4, "status": "Unknown", "rating": "N/A", "date": "2017", "state": "Full Release", "link": "", "note": "The ultimate cultural conglomerate."},
    {"title": "Roblox", "tags": ["Construction", "Sandbox", "Free", "Social", "Party"], "min": 1, "max": 100, "ideal": 1, "status": "Unknown", "rating": "N/A", "date": "2006", "state": "Full Release", "link": "", "note": "More of an engine than a game at this point."},
    {"title": "Agar.io", "tags": ["Casual", "Browser", "Free"], "min": 1, "max": 100, "ideal": 1, "status": "Unknown", "rating": "Mixed", "date": "2015", "state": "Full Release", "link": "https://agar.io/", "note": "The original 'eat or be eaten' browser loop."},
    {"title": "Heavenly Bodies", "tags": ["Physics", "Space", "Co-op", "Puzzle", "Comedy","Simulation"], "min": 1, "max": 2, "ideal": 2, "status": "Unknown", "rating": "Overwhelmingly Positive", "date": "2021", "state": "Full Release", "link": "https://store.steampowered.com/app/1138850/Heavenly_Bodies/", "note": "Zero-G movement is harder than it looks."},
]

def seed_database():
    print("🔬 Aperture Science Database Hard-Link Protocol Initiated.")
    
    db.setup_tables()
    added_count = 0
    tag_count = 0
    
    for game in seed_manifest:
        # Check if game was successfully added (assuming add_game returns an ID or None)
        game_id = db.add_game(
            title=game["title"],
            added_by=0, # System
            # Note: Depending on your DB schema, tags might need to be a string or list
            tags=game["tags"], 
            min_players=game["min"],
            max_players=game["max"],
            ideal_players=game["ideal"],
            # Using the 'status' key we already defined in the manifest
            status=game.get("status", "unknown"), 
            external_rating=game["rating"],
            release_date=game["date"],
            release_state=game["state"],
            notes=game["note"],
            store_link=game["link"]
        )

        if game_id:
            added_count += 1
            # Increment tag count based on the length of the tags list
            tag_count += len(game.get("tags", []))
            print(f"✅ Simulation Archived: {game['title']}")
        else:
            # This triggers if the game already exists in the DB or fails
            print(f"⚠️  Duplicate/Error Simulation: {game['title']}")

    print("--------------------------------------------------")
    print(f"🎉 SUCCESS! {added_count} simulations archived.")
    print(f"🏷️  {tag_count} metadata tags applied.")
    print("Cave Johnson here—we're done. Get back to work.")

def get_unique_tags(manifest):
    unique_tags = set()
    
    for game in manifest:
        # Pull tags from each game entry
        game_tags = game.get("tags", [])
        
        # Add to set (sets automatically ignore duplicates)
        for tag in game_tags:
            unique_tags.add(tag.strip())
            
    # Return a sorted list for better readability
    return sorted(list(unique_tags))

if __name__ == "__main__":
    # Execute and print
    seed_database()
    all_tags = get_unique_tags(seed_manifest)

    print(f"Total Unique Tags: {len(all_tags)}")
    print("----------------------------------")
    for tag in all_tags:
        print(f"- {tag}")