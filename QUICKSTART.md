# Quick Start Guide

Get the Text RPG game running in 5 minutes!

## Step 1: Install Ollama (One-time setup)

1. Download Ollama from https://ollama.ai
2. Install and open Ollama
3. In your terminal, pull the llama2 model:
   ```bash
   ollama pull llama2
   ```

## Step 2: Start Ollama Server

In a terminal, run:
```bash
ollama serve
```

You should see output like:
```
Listening on 127.0.0.1:11434 (http://127.0.0.1:11434)
```

**Leave this terminal running!**

## Step 3: Install Python Dependencies

Open a new terminal and go to the backend directory:
```bash
cd D:\TR\TextRPG\backend
```

Install required packages:
```bash
pip install -r requirements.txt
```

## Step 4: Start the Backend Server

In the same terminal, run:
```bash
python run.py
```

You should see output like:
```
============================================================
Text RPG Backend Server
============================================================

Make sure Ollama is running: 'ollama serve'

Server starting on http://localhost:8000
Frontend available at: http://localhost:8000/frontend/

Press Ctrl+C to stop the server
============================================================
```

**Leave this terminal running too!**

## Step 5: Open the Game

Open your web browser and go to:
```
http://localhost:8000/frontend/
```

✅ **You're ready to play!**

---

## Troubleshooting

### "Cannot connect to backend"
- Make sure the backend server is running (Step 4)
- Check that port 8000 is not in use
- Try refreshing the page

### "Cannot connect to Ollama"
- Make sure Ollama is running (Step 2)
- Check that port 11434 is not in use
- Try the Settings → "Test Ollama Connection" button in the game

### First response is slow
- This is normal! The AI model is running locally and loads on first use
- Subsequent responses will be faster
- On first run, expect 20-30 seconds for the first response

### "llama2 not found"
- Make sure you ran `ollama pull llama2` in Step 1
- Try again: `ollama pull llama2`

---

## What's Happening Behind the Scenes

1. **Ollama** (Terminal 1) - Provides the AI language model (llama2) running on your computer
2. **Backend** (Terminal 2) - FastAPI server that manages game state and talks to Ollama
3. **Frontend** (Your Browser) - Beautiful web interface for playing the game

All data stays on your computer - no internet required after initial setup!

---

## Game Commands

Try these actions:
- "Look around"
- "Check my inventory"
- "Talk to the merchant"
- "Search the area"
- "Rest and heal"
- "Attack the goblin"
- "Explore the forest"

The AI narrator will respond based on your character's current state, equipment, and inventory!

---

## Next Steps

1. **Explore** - Try different actions and see how the story responds
2. **Check Settings** - Configure your character name and Ollama URL
3. **Manage Inventory** - Equip weapons and armor from your starting items
4. **Look at README.md** - Learn about extending the game with custom items, mechanics, etc.

---

## Keyboard Shortcuts

- **Enter** - Submit your action
- **Click "Settings"** - Change character name or test Ollama connection
- **Click "New Game"** - Start fresh (warning: you'll lose all progress)

Enjoy your adventure! 🎮⚔️
