# Doods's Edgy Assistant Bot 🤖🔥

[![Build Verification](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml/badge.svg)](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml)
[![Deploy to Doodlab](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/deploy.yml)

A sovereign, character-based Discord assistant with persistent AI memory, homelab integrations, and maximum chaos potential! 

Features iconic characters from King of the Hill, South Park, and more, powered by Google Gemini AI.

## ✨ Key Features

- **🚀 Full Slash Commands**: Modern discord UX with auto-complete and helpful descriptions.
- **🧠 Persistent AI Memory**: Remembers your conversations forever (stored in SQLite `doodlab.db`).
- **🏠 Homelab Integration**:
  - **Printer Watcher**: Check your 3D printer status (`/printer`) with live webcam snapshots! 📸
  - **Service Monitor**: Check if your internal networks (NAS, Pi-hole, etc.) are up (`/doodlab`).
  - **Request System**: Search and request movies/TV shows via Overseerr (`/request`).
  - **Secure**: Sensitive commands are restricted to authorized users.
- **🎭 9+ AI Characters**: Contextual, in-character responses (not just random quotes).
- **🎁 Gift Registry**: Built-in wishlist system for you and your friends.
- **🛠️ Utility Belt**: QR Code generator, Website pinger, and more.

## 🎭 Available Characters

| Character | Command | Specialty |
|-----------|---------|-----------|
| 🍖 Hank Hill | `/hank` | Propane wisdom and Texas values |
| 🕶️ Dale Gribble | `/dale` | Conspiracy theories and paranoia |
| 😈 Cartman | `/cartman` | Selfish demands and authoritah |
| 🔧 Red Green | `/redgreen` | Duct tape solutions for everything |
| 🖖 Star Trek | `/trek` | Technical sci-fi solutions |
| 📦 Solid Snake | `/snake` | Tactical espionage expertise |
| ⚔️ Kratos | `/kratos` | Godly rage and mythological wisdom |
| 🔥 Dante | `/dante` | Dark poetic wisdom from hell |
| 🤖 AI Chat | `/ai` or `@Bot` | General chat with persistent memory |

## 🚀 Quick Setup

### 1. Requirements
- Python 3.13+
- A Discord Bot Token (with Message Content Intent enabled)
- Google Gemini API Key (Free)

### 2. Installation
```bash
# Clone the repo
git clone https://github.com/yourusername/Doods-Discord-Bot.git
cd Doods-Discord-Bot

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration (.env)
Create a `.env` file in the root directory:
```env
# Homelab Service IPs
PRINTER_IP=your_printer_ip_here
ROUTER_IP=your_router_ip_here
PIHOLE_IP=your_pihole_ip_here
DOODLAB_IP=your_doodlab_ip_here
PLEX_IP=your_plex_ip_here

# 3D Printer services
PRINTER_HOST=your_printer_host(IP+PORT)_here

# --- API URLs (Include http:// and Port) ---
OVERSEERR_URL=your_overseerr_url_here
RADARR_URL=your_radarr_url_here
SONARR_URL=your_sonarr_url_here
LIDARR_URL=your Lidarr_url_here

# Discord Server ID's to send list of / commands to, also updates globally
SERVER_ID=your_server_id_here

# API Keys (Find these in Settings > General > Security)
DISCORD_TOKEN=your_discord_token_here
GEMINI_API_KEY=your_gemini_api_key_here
OVERSEERR_API_KEY=your_overseerr_api_key_here
RADARR_API_KEY=your_radarr_api_key_here
SONARR_API_KEY=your_sonarr_api_key_here
LIDARR_API_KEY=your Lidarr_api_key_here
```

### 4. Customization (Make it Yours!)
This bot is designed to be forked!
- **Change Characters**: Edit `config.py` -> `CHARACTER_PROMPTS` to add your own personas.
- **Change Services**: Edit `config.py` -> `HOMELAB_SERVICES` to list your own internal IPs for `/doodlab` to check.
- **Add Reactions**: Edit `config.py` -> `KEYWORD_REACTIONS` to make the bot react to your server's inside jokes.

### 5. Running
```bash
python main.py
```
*Note: On the first run, it will create `data/doodlab.db` automatically. You can also use this with github runners.*

## 🐳 Docker Deployment
A `docker-compose.yml` is included for easy deployment.
```bash
docker-compose up -d --build
```
Ensure you mount the `/app/data` volume to persist the database!

## 🔒 Security
Homelab commands (`/printer`, `/request`, etc.) are **locked**.
Only users listed in `ALLOWED_USERS` or matching `OWNER_ID` can execute them. Unauthorized users get a polite "Access Denied".

## 🤝 Contributing
Feel free to fork and submit PRs!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request