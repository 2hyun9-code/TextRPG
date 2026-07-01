# Text RPG Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WEB BROWSER                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Frontend (HTML/CSS/JavaScript)             │   │
│  │                                                      │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  │   │
│  │  │   Chat Interface    │  │  Inventory & Stats  │  │   │
│  │  │   - Narrative       │  │  - Equipment slots  │  │   │
│  │  │   - Actions input   │  │  - Item list        │  │   │
│  │  │   - Event messages  │  │  - Quest log        │  │   │
│  │  └─────────────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↕  HTTP REST API                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Backend (Python FastAPI)                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           FastAPI Application                        │   │
│  │                                                      │   │
│  │  Endpoints:                                         │   │
│  │  - /api/game/status        → Get current state     │   │
│  │  - /api/game/new           → Start new game        │   │
│  │  - /api/game/action        → Process player action │   │
│  │  - /api/inventory/*        → Manage inventory      │   │
│  │  - /api/player/*           → Update player info    │   │
│  │                                                      │   │
│  └────────┬─────────────────────────────────────────────┘   │
│           ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Game Logic & State                         │   │
│  │                                                      │   │
│  │  - PlayerState         (HP, attack, level, etc)     │   │
│  │  - Inventory System    (items with effects)         │   │
│  │  - Equipment System    (weapons, armor)             │   │
│  │  - Game Rules          (damage, healing, XP)        │   │
│  │                                                      │   │
│  └────────┬─────────────────────────────────────────────┘   │
│           ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Ollama AI Integration                      │   │
│  │                                                      │   │
│  │  - Generate narrative responses                     │   │
│  │  - Create random quests (if map item owned)         │   │
│  │  - Context-aware storytelling                       │   │
│  │                                                      │   │
│  └────────┬─────────────────────────────────────────────┘   │
│           ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Persistent Storage                         │   │
│  │                                                      │   │
│  │  - player_state.json    (Game save file)            │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↕  HTTP API                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Ollama (Local LLM)                              │
│                                                              │
│  Model: llama2                                              │
│  Purpose: Generate AI narratives and quest descriptions    │
│  Runs locally on port 11434                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### Frontend (`frontend/`)

#### `index.html`
- **Purpose**: Game interface structure
- **Key Elements**:
  - Left panel: Chat/narrative window with message history
  - Right panel: Player stats, equipment, inventory, quests
  - Header: Game title, New Game, Settings buttons
  - Settings modal: Player name and Ollama configuration

#### `style.css`
- **Dark theme** with accent colors (#e74c3c red for actions)
- **Responsive layout** - adapts to smaller screens
- **Animations** - smooth message sliding, HP bar transitions
- **Sections**: Chat, Stats, Equipment slots, Inventory, Quests
- **Custom scrollbars** - themed to match dark aesthetic

#### `script.js`
- **API Communication**: Fetch requests to backend
- **UI Management**: Update player stats, inventory display
- **Event Handling**: Action submission, equipment management
- **Local State**: Message history, loading states
- **Key Functions**:
  - `submitAction()` - Send action to backend
  - `updateUI()` - Refresh all visual elements
  - `equipItem() / unequipItem() / useItem()` - Inventory management

### Backend (`backend/`)

#### `main.py`
- **Framework**: FastAPI with CORS middleware
- **Core Endpoints**:
  - `GET /api/game/status` - Load current game
  - `POST /api/game/new` - Initialize new game
  - `POST /api/game/action` - Process player action
  - `POST /api/inventory/*` - Equip/unequip/use items
  - `POST /api/player/*` - Update player attributes
- **Features**:
  - CORS enabled for frontend communication
  - Static file serving for frontend
  - Auto-save to `player_state.json`

#### `models.py`
- **Data Models** (Pydantic):
  ```
  Item              - Single item with effects
  Inventory         - Collection of items with max slots
  Equipment         - Weapon and armor slots
  PlayerState       - Full player data including stats
  PlayerAction      - Action input from frontend
  AIResponse        - Response from AI narrator
  ```
- **Item Types**: WEAPON, ARMOR, CONSUMABLE, QUEST_ITEM, SPECIAL
- **Methods**: Inventory management (add, remove, check items)

#### `ollama_client.py`
- **Purpose**: Integration with Ollama API
- **Main Features**:
  - `generate_narrative()` - Create story response based on action
  - `generate_special_event()` - Create random quests if map item exists
  - `_build_system_prompt()` - Context-aware prompt construction
  - Includes player stats, equipment, inventory in every request
- **Error Handling**: Graceful fallbacks if Ollama unavailable

#### `requirements.txt`
- FastAPI, Uvicorn (server)
- Pydantic (validation)
- httpx (async HTTP client for Ollama)

## Data Flow

### Action Processing Flow

```
1. User types action in frontend
   ↓
2. JavaScript captures and sends to backend: POST /api/game/action
   ↓
3. Backend receives PlayerAction
   ↓
4. Backend loads current PlayerState from JSON
   ↓
5. Backend calls OllamaClient.generate_narrative()
   ↓
6. OllamaClient builds context-aware prompt with:
   - Player stats (HP, attack, defense)
   - Equipped items (with bonuses)
   - Inventory items
   - Current location
   ↓
7. Ollama processes prompt and returns narrative
   ↓
8. Backend checks for special events (quest generation if map item)
   ↓
9. Backend saves updated PlayerState to JSON
   ↓
10. Backend returns response with narrative + updated player state
   ↓
11. Frontend receives response and updates UI:
   - Adds narrator message to chat
   - Updates player stats display
   - Updates inventory and equipment display
   - Shows special event if occurred
   ↓
12. User sees story and can take next action
```

### Inventory Management

```
Item in Inventory
   ↓ User clicks "Equip"
   ↓
Backend: equipItem()
   ├─ Find item in inventory
   ├─ If weapon: swap with equipped weapon (if exists)
   ├─ Move item to equipment slot
   ├─ Remove from inventory
   ├─ Save state
   └─ Return updated player
   ↓
Frontend: Updates equipment display with item name + bonuses
```

## State Management

### Player State Structure
```json
{
  "name": "Adventurer",
  "level": 1,
  "hp": 100,
  "max_hp": 100,
  "attack": 10,
  "defense": 5,
  "experience": 0,
  "location": "Crossroads Village",
  "inventory": {
    "items": [
      {
        "id": "torch",
        "name": "Wooden Torch",
        "description": "A simple wooden torch",
        "item_type": "consumable",
        "effect": {"light": 1},
        "quantity": 3
      }
    ],
    "max_slots": 20
  },
  "equipment": {
    "weapon": null,
    "armor": null
  },
  "quest_log": []
}
```

## Special Features

### Map Item Quest Generation
When a player has a "map" item (item_type: SPECIAL, id: "map"):
1. After normal narrative generation
2. Backend checks: `player.inventory.has_item("map")`
3. If true, calls `generate_special_event()`
4. Ollama creates brief quest hook
5. Quest is shown as event message in chat

### AI Narrative Context
Every prompt to Ollama includes:
- Current player stats and effective bonuses
- All equipped items with their effects
- Current inventory list
- Current location
- Special items the player has

This allows Ollama to:
- Mention equipment in narrative ("Your sword glints...")
- React to items ("The torch illuminates the cave...")
- Suggest relevant actions ("With the map, you could...")
- Track location changes

## Performance Characteristics

- **First Response**: 15-30 seconds (model loading)
- **Subsequent Responses**: 5-15 seconds (depends on hardware)
- **Frontend Response**: Instant (local JavaScript)
- **Save Operations**: <100ms
- **All processing is local** - no cloud, no internet required

## Extension Points

### Adding New Items
1. Create item in `models.py` or in `create_new_game()`
2. Set appropriate `item_type` (affects how it's used)
3. Add effects dict (e.g., `{"attack_bonus": 5}`)
4. Frontend automatically shows use/equip button based on type

### Modifying AI Behavior
Edit `_build_system_prompt()` in `ollama_client.py`:
- Change system instructions
- Adjust context emphasis (equipment, inventory, location)
- Add new contextual elements

### Adding Game Mechanics
1. Extend `PlayerState` in `models.py`
2. Add methods to handle mechanic (e.g., `take_damage()`)
3. Create endpoint in `main.py` to trigger mechanic
4. Call from frontend when needed

### Custom Model Selection
In `ollama_client.py`:
```python
self.model = "mistral"  # or any Ollama-supported model
```
Pull model first: `ollama pull mistral`

## Security Considerations

- **No authentication** - local development only
- **CORS enabled** - allows frontend communication
- **No input validation** - action text sent directly to LLM
- **File-based saves** - no database, ensure write permissions
- **No secrets** - all API keys hardcoded for localhost

For production deployment, consider:
- Add user authentication
- Validate all inputs before sending to LLM
- Implement proper save mechanisms
- Use environment variables for configuration
