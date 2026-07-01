# Extending the Text RPG Game

This guide shows how to add new features to your Text RPG game.

## Adding New Items

### Example 1: Add a Health Potion

Edit `backend/main.py` in the `create_new_game()` function:

```python
def create_new_game() -> PlayerState:
    player = PlayerState(name="Adventurer")
    
    # ... existing items ...
    
    # Add health potion
    player.inventory.add_item(Item(
        id="health_potion",
        name="Health Potion",
        description="Restores 50 HP when used",
        item_type=ItemType.CONSUMABLE,
        effect={"heal": 50},
        quantity=2
    ))
    
    return player
```

The frontend will automatically show a "Use" button for consumable items. The backend's `/api/inventory/use` endpoint already handles the `heal` effect.

### Example 2: Add an Iron Sword

```python
player.inventory.add_item(Item(
    id="iron_sword",
    name="Iron Sword",
    description="A sharp iron blade that increases attack power",
    item_type=ItemType.WEAPON,
    effect={"attack_bonus": 15},
    quantity=1
))
```

When equipped, the sword's `attack_bonus` is automatically included in the AI's context and player's effective attack stat.

### Example 3: Add a Mana System

In `models.py`, extend `PlayerState`:

```python
class PlayerState(BaseModel):
    name: str = "Adventurer"
    level: int = 1
    hp: int = 100
    max_hp: int = 100
    mana: int = 50  # ADD THIS
    max_mana: int = 50  # ADD THIS
    attack: int = 10
    defense: int = 5
    # ... rest of the class ...
    
    def use_mana(self, amount: int) -> bool:
        if self.mana >= amount:
            self.mana -= amount
            return True
        return False
    
    def restore_mana(self, amount: int) -> None:
        self.mana = min(self.max_mana, self.mana + amount)
```

Update the frontend to display mana in `frontend/script.js`:

```javascript
function updateUI() {
    // ... existing code ...
    
    // Add mana display
    const manaPercent = (currentPlayer.mana / currentPlayer.max_mana) * 100;
    document.getElementById('manaBarFill').style.width = manaPercent + '%';
    document.getElementById('manaValue').textContent = 
        `${currentPlayer.mana}/${currentPlayer.max_mana}`;
}
```

And add to `frontend/index.html` in the player stats section:

```html
<div class="mana-bar-container">
    <div class="mana-bar-label">
        <span>Mana</span>
        <span id="manaValue">50/50</span>
    </div>
    <div class="mana-bar">
        <div class="mana-bar-fill" id="manaBarFill" style="width: 100%; background: linear-gradient(90deg, #3498db, #2980b9);"></div>
    </div>
</div>
```

## Adding New Game Mechanics

### Example: Combat System

Add to `backend/models.py`:

```python
class Enemy(BaseModel):
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    loot: List[Item] = Field(default_factory=list)

class PlayerState(BaseModel):
    # ... existing fields ...
    current_enemy: Optional[Enemy] = None
    
    def attack_enemy(self) -> int:
        # Calculate damage
        base_damage = self.get_effective_attack()
        # Add randomness
        import random
        actual_damage = random.randint(int(base_damage * 0.8), int(base_damage * 1.2))
        return actual_damage
    
    def is_in_combat(self) -> bool:
        return self.current_enemy is not None
```

Add endpoint to `backend/main.py`:

```python
@app.post("/api/game/attack-enemy")
async def attack_enemy():
    player = load_player_state()
    
    if not player.is_in_combat():
        raise HTTPException(status_code=400, detail="Not in combat")
    
    damage_dealt = player.attack_enemy()
    player.current_enemy.hp -= damage_dealt
    
    # Check if enemy defeated
    if player.current_enemy.hp <= 0:
        # Add loot to inventory
        for item in player.current_enemy.loot:
            player.inventory.add_item(item)
        
        player.experience += 50
        player.current_enemy = None
        message = f"Victory! You dealt {damage_dealt} damage and defeated the {player.current_enemy.name}!"
    else:
        # Enemy counterattacks
        enemy_damage = player.take_damage(player.current_enemy.attack)
        message = f"You dealt {damage_dealt} damage! Enemy counterattacks for {enemy_damage} damage."
    
    save_player_state(player)
    return {"message": message, "player": player.dict()}
```

### Example: Experience and Leveling

Add to `backend/models.py`:

```python
class PlayerState(BaseModel):
    # ... existing fields ...
    experience: int = 0
    experience_for_next_level: int = 100
    
    def gain_experience(self, amount: int) -> bool:
        self.experience += amount
        
        if self.experience >= self.experience_for_next_level:
            self.level_up()
            return True
        return False
    
    def level_up(self) -> None:
        self.level += 1
        self.experience = 0
        self.max_hp += 10
        self.hp = self.max_hp
        self.attack += 2
        self.defense += 1
        self.experience_for_next_level = int(self.experience_for_next_level * 1.2)
```

## Modifying AI Behavior

### Making the AI More Dramatic

Edit `backend/ollama_client.py`:

```python
def _build_system_prompt(self, player_state: PlayerState) -> str:
    # ... existing code ...
    return f"""You are an epic fantasy narrator for a text RPG adventure. 
The player is {player_state.name}, Level {player_state.level}.

Current Status:
- HP: {player_state.hp}/{player_state.max_hp}
- Attack: {player_state.get_effective_attack()}
- Defense: {player_state.defense}
- Location: {player_state.location}
- {weapon_info}
- {armor_info}
- {special_info}

Inventory ({len(player_state.inventory.items)}/{player_state.inventory.max_slots}):
{self._format_inventory(player_state)}

Instructions:
1. RESPOND WITH DRAMATIC FLAIR - Use vivid descriptions and action words
2. Keep responses concise (2-3 sentences) but IMPACTFUL
3. React theatrically to equipped items - make them feel POWERFUL
4. If the player has a map item, SUGGEST DANGEROUS ADVENTURES
5. Use sound effects occasionally (CRASH! WHOOSH! etc)
6. Make the player feel like the hero of an EPIC SAGA
7. Suggest dramatic next actions with exciting possibilities"""
```

### Making the AI More Helpful

```python
def _build_system_prompt(self, player_state: PlayerState) -> str:
    # ... existing code ...
    return f"""You are a helpful and encouraging narrator for a text RPG game.

Current Status:
- HP: {player_state.hp}/{player_state.max_hp}
- Location: {player_state.location}
- Inventory: {len(player_state.inventory.items)} items

Instructions:
1. Describe the results of the player's action clearly
2. Always provide at least one suggested next action
3. Remind the player of useful abilities they have
4. Be encouraging and fun
5. If an action is unclear, ask for clarification
6. Suggest using items or equipment when appropriate"""
```

## Adding New Item Types

Extend the `ItemType` enum in `backend/models.py`:

```python
class ItemType(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    QUEST_ITEM = "quest_item"
    SPECIAL = "special"
    SPELL = "spell"  # NEW
    ACCESSORY = "accessory"  # NEW
    KEY = "key"  # NEW
```

Then handle new types in the frontend and backend as needed.

## Adding Locations

Track location in actions:

```python
@app.post("/api/game/travel")
async def travel_to_location(location: str):
    player = load_player_state()
    
    valid_locations = [
        "Crossroads Village",
        "Dark Forest",
        "Mountain Peak",
        "Mysterious Cave",
        "Seaside Town"
    ]
    
    if location not in valid_locations:
        raise HTTPException(status_code=400, detail="Invalid location")
    
    player.location = location
    
    narrative = await ollama.generate_narrative(
        player, 
        f"Travel to {location}"
    )
    
    save_player_state(player)
    
    return {
        "narrative": narrative,
        "player": player.dict()
    }
```

## Adding Save/Load Slots

Modify `backend/main.py`:

```python
import os

SAVE_DIR = "saves"
os.makedirs(SAVE_DIR, exist_ok=True)

def load_player_state(slot: int = 0) -> PlayerState:
    save_file = f"{SAVE_DIR}/save_{slot}.json"
    if os.path.exists(save_file):
        with open(save_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return PlayerState(**data)
    return create_new_game()

def save_player_state(player: PlayerState, slot: int = 0) -> None:
    save_file = f"{SAVE_DIR}/save_{slot}.json"
    with open(save_file, "w", encoding="utf-8") as f:
        json.dump(player.dict(), f, ensure_ascii=False, indent=2)

@app.get("/api/game/slots")
async def get_save_slots():
    slots = []
    for i in range(5):
        path = f"{SAVE_DIR}/save_{i}.json"
        if os.path.exists(path):
            slots.append({"slot": i, "exists": True})
        else:
            slots.append({"slot": i, "exists": False})
    return {"slots": slots}

@app.post("/api/game/load-slot")
async def load_slot(slot: int):
    # ... implementation ...
    pass
```

## Adding Dialogue with NPCs

```python
class NPC(BaseModel):
    name: str
    dialogue: List[str]
    quest: Optional[str] = None

@app.post("/api/npc/talk")
async def talk_to_npc(npc_name: str):
    player = load_player_state()
    
    npcs = {
        "merchant": NPC(
            name="Merchant",
            dialogue=[
                "Welcome to my shop!",
                "I have fine wares if you have coin.",
                "The road ahead is dangerous, stay alert."
            ]
        )
    }
    
    if npc_name not in npcs:
        raise HTTPException(status_code=404, detail="NPC not found")
    
    npc = npcs[npc_name]
    import random
    dialogue = random.choice(npc.dialogue)
    
    return {"npc": npc_name, "dialogue": dialogue}
```

## Adding Achievements/Badges

In `backend/models.py`:

```python
class Achievement(BaseModel):
    id: str
    name: str
    description: str
    earned: bool = False
    earned_at: Optional[datetime] = None

class PlayerState(BaseModel):
    # ... existing fields ...
    achievements: List[Achievement] = Field(default_factory=list)
    
    def unlock_achievement(self, achievement_id: str) -> bool:
        achievement = next(
            (a for a in self.achievements if a.id == achievement_id), 
            None
        )
        if achievement and not achievement.earned:
            achievement.earned = True
            achievement.earned_at = datetime.now()
            return True
        return False
```

## Tips for Extension

1. **Keep AI prompts concise** - Shorter prompts = faster responses
2. **Test locally first** - Run the backend/frontend locally before deploying
3. **Save after state changes** - Always call `save_player_state()` after modifying player
4. **Use item effects dict** - Effects like `{"attack_bonus": 5}` are flexible
5. **Update frontend UI incrementally** - Test each change
6. **Use meaningful item IDs** - Makes debugging easier (e.g., "iron_sword" not "item1")
7. **Document custom mechanics** - Future you will thank present you!

## Common Patterns

### Check if player has specific item
```python
if player.inventory.has_item("map"):
    # Do something
```

### Add item to inventory
```python
new_item = Item(id="key", name="Golden Key", ...)
player.inventory.add_item(new_item)
```

### Calculate effective stat
```python
effective_attack = player.get_effective_attack()  # Includes equipment bonuses
```

### Update in-game narrative
```python
narrative = await ollama.generate_narrative(player, "Specific action here")
addNarratorMessage(narrative);  # From frontend
```

Enjoy building your epic adventure! 🎮⚔️
