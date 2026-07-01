from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import os
from pathlib import Path
import sys
from models import (
    PlayerState, PlayerAction, Item, ItemType, Equipment, Inventory,
    AIResponse, GameMessage
)
from ollama_client import OllamaClient

app = FastAPI(title="Text RPG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ollama = OllamaClient()

SAVE_FILE = "player_state.json"


def load_player_state() -> PlayerState:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return PlayerState(**data)
    return create_new_game()


def create_new_game() -> PlayerState:
    player = PlayerState(name="모험가")
    player.inventory.add_item(Item(
        id="torch",
        name="나무 횃불",
        description="단순한 나무로 만든 횃불",
        item_type=ItemType.CONSUMABLE,
        effect={"light": 1},
        quantity=3
    ))
    player.inventory.add_item(Item(
        id="map",
        name="낡은 지도",
        description="근처 땅을 보여주는 오래된 지도",
        item_type=ItemType.SPECIAL,
        effect={"reveals_quests": True}
    ))
    return player


def save_player_state(player: PlayerState) -> None:
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(player.dict(), f, ensure_ascii=False, indent=2)


@app.on_event("startup")
async def startup():
    pass


@app.on_event("shutdown")
async def shutdown():
    await ollama.close()


@app.get("/api/game/status")
async def get_game_status():
    player = load_player_state()
    return {
        "player": player.dict(),
        "message": f"{player.name}님 환영합니다! 당신은 {player.location}에 있습니다."
    }


@app.post("/api/game/new")
async def new_game():
    player = create_new_game()
    save_player_state(player)
    return {"player": player.dict(), "message": "새 게임이 시작되었습니다!"}


@app.post("/api/game/action")
async def perform_action(action: PlayerAction):
    player = load_player_state()

    if player.hp <= 0:
        raise HTTPException(status_code=400, detail="플레이어가 패배했습니다. 새 게임을 시작하세요.")

    narrative = await ollama.generate_narrative(player, action.action)

    special_event = await ollama.generate_special_event(player)

    save_player_state(player)

    response_data = {
        "narrative": narrative,
        "player": player.dict(),
    }

    if special_event:
        response_data["special_event"] = special_event

    return response_data


@app.post("/api/inventory/equip")
async def equip_item(item_id: str):
    player = load_player_state()

    item = next((i for i in player.inventory.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    if item.item_type == ItemType.WEAPON:
        if player.equipment.weapon:
            player.inventory.add_item(player.equipment.weapon)
        player.equipment.weapon = item
        player.inventory.remove_item(item_id, 1)
        save_player_state(player)
        return {
            "message": f"{item.name}을(를) 장착했습니다",
            "player": player.dict()
        }
    elif item.item_type == ItemType.ARMOR:
        if player.equipment.armor:
            player.inventory.add_item(player.equipment.armor)
        player.equipment.armor = item
        player.inventory.remove_item(item_id, 1)
        save_player_state(player)
        return {
            "message": f"{item.name}을(를) 장착했습니다",
            "player": player.dict()
        }
    else:
        raise HTTPException(status_code=400, detail="이 아이템 타입은 장착할 수 없습니다")


@app.post("/api/inventory/unequip")
async def unequip_item(slot: str):
    player = load_player_state()

    if slot == "weapon":
        if player.equipment.weapon:
            player.inventory.add_item(player.equipment.weapon)
            player.equipment.weapon = None
        else:
            raise HTTPException(status_code=400, detail="장착된 무기가 없습니다")
    elif slot == "armor":
        if player.equipment.armor:
            player.inventory.add_item(player.equipment.armor)
            player.equipment.armor = None
        else:
            raise HTTPException(status_code=400, detail="장착된 방어구가 없습니다")
    else:
        raise HTTPException(status_code=400, detail="유효하지 않은 슬롯입니다")

    save_player_state(player)
    return {
        "message": f"{slot}에서 장착을 해제했습니다",
        "player": player.dict()
    }


@app.post("/api/inventory/use")
async def use_item(item_id: str):
    player = load_player_state()

    item = next((i for i in player.inventory.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    if item.item_type != ItemType.CONSUMABLE:
        raise HTTPException(status_code=400, detail="소비용 아이템만 사용할 수 있습니다")

    effect = item.effect
    if "heal" in effect:
        player.heal(effect["heal"])
    if "light" in effect:
        pass

    player.inventory.remove_item(item_id, 1)
    save_player_state(player)

    return {
        "message": f"{item.name}을(를) 사용했습니다",
        "player": player.dict()
    }


@app.post("/api/player/update-name")
async def update_player_name(name: str):
    player = load_player_state()
    player.name = name
    save_player_state(player)
    return {"player": player.dict()}


@app.post("/api/debug/add-item")
async def debug_add_item(item_id: str, name: str, quantity: int = 1):
    player = load_player_state()
    new_item = Item(
        id=item_id,
        name=name,
        description=f"테스트 아이템: {name}",
        item_type=ItemType.CONSUMABLE,
        effect={"test": True},
        quantity=quantity
    )
    player.inventory.add_item(new_item)
    save_player_state(player)
    return {"player": player.dict()}


frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
