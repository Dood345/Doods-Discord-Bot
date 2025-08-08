# Discord Bot Setup Guide

## Prerequisites

1. Python 3.8 or higher
2. A Discord account
3. Basic terminal/command line knowledge

## Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give it a name (like "Shenanigans Bot")
4. Go to the "Bot" section
5. Click "Add Bot"
6. Under "Token", click "Copy" and save this token securely
7. Enable "Message Content Intent" in the bot settings

## Step 2: Install Dependencies

Create a `requirements.txt` file:
```
discord.py>=2.3.0
python-dotenv>=1.0.0
google-generativeai>=0.3.0
asyncio
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Step 3: Environment Setup

Create a `.env` file in your project directory:
```
DISCORD_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Getting a Gemini API Key (Optional but Recommended):
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key and add it to your `.env` file
4. The bot will work without AI, but responses will be much more fun with it!

## Step 4: Invite Bot to Server

1. In Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes: `bot`
3. Select bot permissions: 
   - Send Messages
   - Use Slash Commands
   - Add Reactions
   - Embed Links
   - Read Message History
4. Copy the generated URL and open it to invite the bot

## Step 5: Run the Bot

Update the bottom of your main bot file:
```python
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in .env file")
    else:
        bot.run(token)
```

Then run:
```bash
python bot.py
```

## Current Commands (Now with AI!)

### Basic Commands (work without AI)
- `!help` - Show all commands
- `!whatgame` - Random game picker  
- `!gamevote [games]` - Start a game vote
- `!flubber <text>` - Make text bouncy
- `!terminate [target]` - Threat assessment
- `!beer` - Beer recommendations
- `!conspiracy` - Generate conspiracy theories
- `!propane` - Propane facts

### AI-Enhanced Commands (smarter with Gemini API)
- `!hank [message]` - Hank Hill responses (try: `!hank my lawn is dying`)
- `!dale [message]` - Dale Gribble conspiracy theories (try: `!dale the internet is down`) 
- `!cartman [message]` - Cartman being Cartman (try: `!cartman I don't want to do homework`)
- `!redgreen [problem]` - Red Green duct tape solutions (try: `!redgreen my car won't start`)
- `!trek [problem]` - Star Trek technical solutions (try: `!trek the computer is frozen`)
- `!ai <question>` - Ask AI anything (random character style)

### New AI Features:
- Characters now respond contextually to what you say!
- Much more varied and entertaining responses
- Falls back to static responses if AI isn't configured

## Next Steps

This is just the foundation! We can add:
- AI integration (Gemini/OpenAI)
- Custom emotes
- Soundboard integration
- Database storage
- More interactive features
- Dune spice trading game
- Member-specific roasting
- And much more!

## Security Notes

- Never commit your `.env` file to version control
- Keep your bot token secret
- Consider using a database for persistent data
