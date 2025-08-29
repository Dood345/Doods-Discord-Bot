# Deploy Discord Bot to Railway.app

Switched to render.com for their free tier, despite the spindown issues. You can still use railway.app for 30days of uptime.

## Step 1: Prepare Your Code

Create these files in your project directory:

### `requirements.txt`
```
discord.py>=2.3.0
python-dotenv>=1.0.0
google-generativeai>=0.3.0
```

### `Procfile` (tells Railway how to run your bot)
```
worker: python bot.py
```

### `.gitignore`
```
.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.log
```

## Step 2: Push to GitHub

```bash
git init
git add .
git commit -m "Initial Discord bot commit"
git branch -M main
git remote add origin https://github.com/yourusername/discord-satan.git
git push -u origin main
```

## Step 3: Deploy to Railway

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your bot repository
6. Railway will automatically detect it's a Python project

## Step 4: Add Environment Variables

In Railway dashboard:
1. Go to your project
2. Click "Variables" tab
3. Add:
   - `DISCORD_TOKEN` = your_discord_token
   - `GEMINI_API_KEY` = your_gemini_key

## Step 5: Deploy!

Railway will automatically:
- Install dependencies from requirements.txt
- Run your bot using the Procfile
- Keep it running 24/7

## Alternative: One-Click Deploy

You can also create a Railway button for instant deployment!

## Monitoring

- Check logs in Railway dashboard
- Bot will auto-restart if it crashes
- Easy to redeploy when you push new code

## Cost

- **Free tier**: 500 hours/month (plenty for a Discord bot)
- **Pro plan**: $5/month for unlimited hours if needed

## Benefits

✅ Zero server management  
✅ Automatic deployments  
✅ Built-in monitoring  
✅ Environment variable management  
✅ Free SSL certificates  
✅ Easy scaling  

Your bot will be online 24/7 without you having to manage any servers!
