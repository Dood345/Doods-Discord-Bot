# Doods's Shenanigans Discord Bot 🤖🔥

A character-based Discord bot with AI personality responses, conversation memory, and maximum chaos potential! Features iconic characters from King of the Hill, South Park, Red Green Show, Star Trek, Metal Gear Solid, God of War, and Dante's Inferno.

## ✨ Key Features

- **AI-Powered Characters**: 9 unique personalities with contextual responses
- **Conversation Memory**: AI remembers your chat history for better responses
- **Smart Keyword Reactions**: Auto-reacts with emojis based on message content
- **Social Features**: Roast and compliment system with character-specific responses
- **Game Tools**: Random game picker and voting system
- **Fallback System**: Works great even without AI configuration

## 🎭 Available Characters

| Character | Command | Specialty |
|-----------|---------|-----------|
| 🍖 Hank Hill | `!hank` | Propane wisdom and Texas values |
| 🕶️ Dale Gribble | `!dale` | Conspiracy theories and paranoia |
| 😈 Cartman | `!cartman` | Selfish demands and authoritah |
| 🔧 Red Green | `!redgreen` | Duct tape solutions for everything |
| 🖖 Star Trek Officer | `!trek` | Technical sci-fi solutions |
| 🚨 Alex Jones | `!conspiracy` | Over-the-top conspiracy theories |
| 📦 Solid Snake | `!snake` | Tactical espionage expertise |
| ⚔️ Kratos | `!kratos` | Godly rage and mythological wisdom |
| 🔥 Dante | `!dante` | Dark poetic wisdom from hell |

## 📋 Prerequisites

1. **Python 3.8+**
2. **Discord account**
3. **Basic terminal knowledge**

## 🚀 Quick Setup

### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** → Name it (e.g., "Satan's Shenanigans Bot")
3. Go to **"Bot"** section → Click **"Add Bot"**
4. Copy the **Token** and save it securely
5. Enable **"Message Content Intent"** in bot settings

### Step 2: Project Structure

Create this directory structure:

```
discord_bot/
├── main.py                    # Main bot file
├── config.py                  # Configuration and data
├── requirements.txt           # Dependencies
├── .env                       # Environment variables
├── utils/
│   ├── __init__.py
│   ├── ai_handler.py         # AI integration
│   └── reaction_handler.py   # Message reactions
└── commands/
    ├── __init__.py
    ├── character_commands.py  # Character personalities
    ├── social_commands.py     # Roasts & compliments
    ├── game_commands.py       # Game features
    └── misc_commands.py       # Utilities & help
```

### Step 3: Install Dependencies

Create `requirements.txt`:
```
discord.py==2.3.2
google-generativeai==0.3.2
python-dotenv==1.0.0
asyncio
```

Install:
```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration

Create `.env` file:
```env
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

#### Getting Gemini API Key (Recommended):
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click **"Create API Key"**
3. Copy and add to `.env` file
4. *Bot works without AI, but responses are much funnier with it!*

### Step 5: Invite Bot to Server

1. In Discord Developer Portal: **OAuth2** → **URL Generator**
2. Select scopes: `bot`
3. Select permissions: 
   - Send Messages
   - Add Reactions  
   - Embed Links
   - Read Message History
4. Use generated URL to invite bot

### Step 6: Run the Bot

```bash
python main.py
```

## 🎮 Commands Reference

### 👥 Social Features
- `!roast @user` - Character-based roasting system
- `!roastme` - Roast yourself
- `!compliment @user` - Character-based compliments

### 🎭 Character AI (Enhanced with Messages!)
- `!hank [message]` - *"That propane ain't right, I tell you what!"*
- `!dale [message]` - *"The government is behind your WiFi problems!"*
- `!cartman [message]` - *"Respect my authoritah!"*
- `!redgreen [problem]` - *"Just need some duct tape and a 2x4..."*
- `!trek [problem]` - *"Have you tried reversing the polarity?"*
- `!snake [message]` - *"Colonel, we have a situation..."*
- `!kratos [message]` - *"BOY! Listen carefully..."*
- `!dante [message]` - *"Your sins have earned you a place in..."*

### 🎮 Games & Entertainment
- `!whatgame` - Random game picker
- `!gamevote [games]` - Start voting poll
- `!gameslist` - Show all available games
- `!addgame <name>` - Suggest new games
- `!flubber <text>` - BoUnCy TeXt TrAnSfOrMeR
- `!beer [preferences]` - AI-powered beer recommendations

### 🤖 AI & Tech Features  
- `!ai <question>` - **Chat with memory!** AI remembers your conversation
- `!clearhistory` - Reset your AI conversation memory
- `!terminate [target]` - Terminator threat assessment
- `!conspiracy [topic]` - Generate wild conspiracy theories

### 😄 Utilities & Info
- `!propane` - Random propane facts (Hank approved)
- `!emote <keyword>` - Test keyword reactions
- `!keywords` - Show all reaction keywords  
- `!ping` - Check bot response time
- `!about` - Bot statistics and info
- `!help [command]` - Command help (specific or general)

## 🎯 Pro Tips

### AI Conversation Memory
The `!ai` command now **remembers your chat history**! Have actual conversations:
```
You: !ai what's your favorite color?
Bot: I'd say electric blue - reminds me of quality code syntax highlighting.

You: !ai why that specific shade?
Bot: Well, from our previous chat about colors, electric blue just has that perfect balance...
```

### Enhanced Character Responses  
Characters are much smarter with AI! Try contextual messages:
```
!hank my lawn is dying
!dale the internet keeps going out
!redgreen my car won't start
!kratos I failed my exam
!dante I told a lie today
```

### Automatic Reactions
Bot automatically reacts to keywords with emojis:
- "propane" → 🔥🍖⛽
- "beer" → 🍺🍻🥴  
- "ai" → 🤖🧠💻
- "snake" → 📦❗🐍
- And 50+ more!

## 🔧 Advanced Configuration

### Reaction Settings
Edit `config.py` to adjust:
```python
REACTION_CHANCE = 25  # 25% chance to react to keywords
```

### Adding New Characters
The modular system makes adding characters easy:

1. Add character prompt to `config.py`
2. Add fallback quotes
3. Add character info (name, emoji)
4. Create command in `character_commands.py`

### Custom Keywords  
Add new reaction keywords in `config.py`:
```python
KEYWORD_REACTIONS = {
    'your_keyword': ['🎯', '⚡', '🎮'],
    # ... existing keywords
}
```

## 🛡️ Security & Best Practices

- **Never commit `.env` to version control**
- Keep bot token secure and private
- Add `.env` to your `.gitignore`:
  ```gitignore
  .env
  __pycache__/
  *.pyc
  ```
- Consider using environment-specific configs for development/production

## 🎪 What Makes This Bot Special

### 1. **Personality-Driven Design**
Each character has distinct personalities with contextual AI responses, not just random quotes.

### 2. **Conversation Memory** 
Unlike basic bots, this remembers your AI conversations for more natural interactions.

### 3. **Graceful Degradation**
Works great with or without AI - fallback systems ensure functionality.

### 4. **Modular Architecture**
Easy to maintain, expand, and customize. Adding new features is straightforward.

### 5. **Private Server Optimized**
Built for small groups of friends who want maximum entertainment value.

## 🚀 Future Expansion Ideas

- **Voice integration** with character sound effects
- **Custom soundboard** for each character  
- **Database integration** for persistent user data
- **Mini-games** and interactive features
- **Scheduled events** and reminders
- **Custom server-specific inside jokes**
- **Integration with other APIs** (weather, news, etc.)

## 🐛 Troubleshooting

### Common Issues:

**Bot doesn't respond:**
- Check token in `.env`
- Ensure "Message Content Intent" is enabled
- Verify bot has proper permissions

**AI responses not working:**
- Check `GEMINI_API_KEY` in `.env`
- Bot will fallback to static responses automatically

**Import errors:**
- Ensure all `__init__.py` files exist in directories
- Check Python path and virtual environment

**Permission errors:**
- Bot needs "Send Messages", "Add Reactions", "Embed Links" permissions
- Check server-specific permission overrides

---

**Ready to cause maximum shenanigans?** 🔥  
*"That's a clean-burning bot, I tell you what!"* - Hank Hill (probably)

---

[![Build Verification](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml/badge.svg)](https://github.com/Dood345/Doods-Discord-Bot/actions/workflows/build.yml)