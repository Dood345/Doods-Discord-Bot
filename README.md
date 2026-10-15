# Doods's Edgy Assistant Bot 🤖🔥

[![Build Verification](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml/badge.svg)](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml)
[![Deploy to Doodlab](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/deploy.yml)

A sovereign, character-based Discord assistant with persistent AI memory, homelab integrations, and maximum chaos potential! 

Features iconic characters from King of the Hill, South Park, and more, powered by a self-hosted LLM via [Ollama](https://ollama.com).

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
- Python 3.14+
- A Discord Bot Token (with Message Content Intent enabled)
- An [Ollama](https://ollama.com) server with the chat model pulled (see `model_name` in `utils/ai_handler.py`)
- Optional: ComfyUI (image generation), ffmpeg (music)

### 2. Installation
We use [Astral's `uv`](https://docs.astral.sh/uv/) for lightning-fast, deterministic dependency management.

```bash
# Clone the repo
git clone https://github.com/yourusername/Doods-Discord-Bot.git
cd Doods-Discord-Bot

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync the virtual environment
uv sync
```

### 3. Configuration (.env)
Copy `.env.example` to `.env` and fill in the values you need. Only `DISCORD_TOKEN` is required; AI, image, music and homelab features disable themselves when their settings are missing.

```bash
cp .env.example .env
```

### 4. Customization (Make it Yours!)
This bot is designed to be forked!
- **Change Characters**: Edit `config.py` -> `CHARACTER_PROMPTS` to add your own personas.
- **Server Contexts**: Copy `data/server_contexts.example.json` to `data/server_contexts.json` (gitignored) and map your guild IDs to per-server persona text.
- **Add Reactions**: Edit `config.py` -> `KEYWORD_REACTIONS` to make the bot react to your server's inside jokes.

### 5. Running
Use `uv run` to ensure the bot perfectly executes within the isolated environment.

**On Windows (Development):**
If `uv` is not inherently in your system PATH after installation, route it explicitly through Python:
```bash
python -m uv run python main.py
```

**On Linux / Mac (or if Windows PATH is configured):**
```bash
uv run python main.py
```
*Note: On the first run, it will create `data/doodlab.db` automatically.*

## 🧪 Testing

The Aperture Science Mainframe includes a rigorous automated test suite covering the Core Data layer and the AI Handler logic. We mock external API requirements to ensure tests can be run anywhere.

**On Windows (Development):**
```bash
# Run the test suite
python -m uv run pytest -v

# Run the test suite and generate a coverage report
python -m uv run pytest -v --cov=utils --cov=services
```

**On Linux / Mac:**
```bash
# Run the test suite
uv run pytest -v

# Run the test suite and generate a coverage report
uv run pytest -v --cov=utils --cov=services
```

## 🚀 Deployment (GitHub Runner)

We rely on **GitHub Actions** and an internal self-hosted runner to automatically deploy to the homelab, eliminating the need for Docker containers.

When you push to the `main` branch, `.github/workflows/deploy.yml` triggers:
1. Uses `rsync` to synchronize your local network files (preserving your `.env` and `data/` directory).
2. Updates `uv` and executes `uv sync` on the remote runner to instantaneously resolve newly added dependencies.
3. Restarts the system service (`sudo systemctl restart discordBot.service`).

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