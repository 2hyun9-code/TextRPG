# Text RPG Adventure with Ollama

A browser-based text RPG game that integrates with Ollama for AI-driven narrative generation. The game features a clean split-panel interface with chat-based storytelling on the left and inventory/equipment management on the right.

## Features

- **AI-Driven Narrative**: Uses Ollama (llama2 model) to generate dynamic, context-aware story responses
- **Player Progression**: Track health, attack, defense, level, and experience
- **Inventory System**: Manage items with limited inventory slots
- **Equipment System**: Equip weapons and armor with stat bonuses
- **Special Events**: Random quests generated when you have a map item
- **Persistent Save**: Game state is automatically saved to JSON
- **Clean UI**: Dark-themed, responsive web interface

## Project Structure

```
TextRPG/
├── backend/
│   ├── main.py           # FastAPI server with game logic
│   ├── models.py         # Pydantic models for game state
│   ├── ollama_client.py  # Ollama API integration
│   ├── requirements.txt  # Python dependencies
│   └── player_state.json # Auto-generated save file
├── frontend/
│   ├── index.html        # Main game interface
│   ├── style.css         # Styling (dark theme)
│   └── script.js         # Game logic and API communication
└── README.md
```

## Prerequisites

### Required Software
- **Python 3.8+**
- **Ollama** (https://ollama.ai) - for local LLM
- **Modern web browser** (Chrome, Firefox, Edge, Safari)

### Setup Instructions

#### 1. Install Ollama
Download and install Ollama from https://ollama.ai

After installation, pull the llama2 model:
```bash
ollama pull llama2
```

#### 2. Start Ollama Server
In a terminal, start the Ollama server:
```bash
ollama serve
```
The server will run on `http://localhost:11434`

#### 3. Setup Python Backend

Clone or navigate to the TextRPG directory:
```bash
cd D:\TR\TextRPG\backend
```

Create a virtual environment (optional but recommended):
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the FastAPI server:
```bash
python main.py
```
The backend will run on `http://localhost:8000`

#### 4. Open the Game
1. Open `frontend/index.html` in your web browser
   - You can drag the file to your browser, or
   - Use a local HTTP server (recommended):
     ```bash
     # From the TextRPG directory:
     python -m http.server 8080
     ```
   - Then open `http://localhost:8080/frontend/`

## How to Play

### Basic Commands
- Type actions like "look around", "talk to the merchant", "attack the goblin"
- The AI narrator will respond to your actions based on your character state

### Inventory Management
- **Equip**: Click "Equip" on weapons/armor in your inventory
- **Use**: Click "Use" on consumable items
- **Unequip**: Click "Unequip" buttons in the equipment slots

### Character Stats
- **HP**: Health points - reach 0 and the game ends
- **Attack**: Damage dealt to enemies (increased by equipped weapons)
- **Defense**: Damage reduction (increased by equipped armor)
- **Level**: Your character progression

### Special Features
- If you have a **Map** item in inventory, the AI may randomly generate special quests
- Different equipment provides different bonuses
- The narrator takes inventory state into account when generating responses

## Configuration

### Player Settings
Click the "Settings" button to:
- Change your character name
- Adjust Ollama server URL (default: `http://localhost:11434`)
- Test Ollama connection

### Game Settings (in backend/main.py)
- Modify `SAVE_FILE` to change the save location
- Adjust `PlayerState` defaults for different starting configurations
- Change the Ollama model in `OllamaClient.__init__()`

## API Endpoints

### Game
- `GET /api/game/status` - Get current game state
- `POST /api/game/new` - Start a new game
- `POST /api/game/action` - Perform an action (core gameplay)

### Inventory
- `POST /api/inventory/equip?item_id=<id>` - Equip an item
- `POST /api/inventory/unequip?slot=<weapon|armor>` - Unequip an item
- `POST /api/inventory/use?item_id=<id>` - Use a consumable item

### Player
- `POST /api/player/update-name?name=<name>` - Change character name

## Troubleshooting

### "Cannot connect to backend"
- Make sure the FastAPI server is running on port 8000
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Look for error messages in the backend console

### "Cannot connect to Ollama"
- Make sure Ollama is running: `ollama serve`
- Verify llama2 is installed: `ollama list`
- Check that Ollama is accessible on `http://localhost:11434`
- Use Settings → Test Ollama Connection to diagnose

### AI responses are slow
- Ollama runs locally, so responses depend on your hardware
- Ensure no other resource-heavy processes are running
- Consider using a smaller model if needed (e.g., `orca-mini`)

### Save file issues
- The game saves automatically to `backend/player_state.json`
- To reset, simply delete this file and refresh the browser
- Make sure the backend has write permissions to the directory

## Extending the Game

### Add New Items
Edit `backend/main.py` in the `create_new_game()` function:
```python
player.inventory.add_item(Item(
    id="sword",
    name="Iron Sword",
    description="A sharp iron blade",
    item_type=ItemType.WEAPON,
    effect={"attack_bonus": 5},
    quantity=1
))
```

### Modify AI Behavior
Edit the `_build_system_prompt()` method in `backend/ollama_client.py` to change how the narrator describes the story.

### Add Status Effects
Extend the `PlayerState` class in `models.py` to track additional attributes like mana, stamina, or status conditions.

## Performance Notes

- **First response**: ~10-30 seconds (model loading)
- **Subsequent responses**: ~5-15 seconds (depends on hardware)
- Frontend communicates with backend via REST API
- All processing happens locally - no internet required

## License

This project is provided as-is for educational and personal use.

## Future Enhancements

- [ ] Combat system with AI opponents
- [ ] Branching narrative choices
- [ ] Skill/ability system
- [ ] Party members/companions
- [ ] Dungeon/cave exploration with randomized layouts
- [ ] Trading system with merchants
- [ ] Achievement/trophy system
- [ ] Multiplayer support

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Ensure all prerequisites are installed and running
3. Review the browser console (F12) for JavaScript errors
4. Check the backend console for server errors
