from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import os
import random
from pathlib import Path
from typing import Optional
from models import (
    PlayerState, PlayerAction, Item, ItemType, Equipment, Inventory,
    AIResponse, GameMessage, JobClass, Enemy
)
from ollama_client import OllamaClient
from items_db import ITEMS_DB, SHOP_STOCK, create_item, get_item_price
from enemies_db import get_random_enemy, roll_drop

app = FastAPI(title="Text RPG")


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

ollama = OllamaClient()

SAVE_FILE = "player_state.json"
BACKUP_FILE = "player_state.backup.json"

# 메모리 캐시 - 매 요청마다 파일을 읽지 않도록 최적화
_player_cache: Optional[PlayerState] = None


def _read_save_file(path: str) -> Optional[PlayerState]:
    """저장 파일을 안전하게 읽기. 손상되었으면 None 반환"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return PlayerState(**data)
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def load_player_state() -> PlayerState:
    global _player_cache

    # 1순위: 메모리 캐시
    if _player_cache is not None:
        return _player_cache

    # 2순위: 저장 파일
    if os.path.exists(SAVE_FILE):
        player = _read_save_file(SAVE_FILE)
        if player is not None:
            _player_cache = player
            return player
        # 저장 파일 손상 -> 백업에서 복구 시도
        print("경고: 저장 파일이 손상되었습니다. 백업에서 복구를 시도합니다.")

    # 3순위: 백업 파일
    if os.path.exists(BACKUP_FILE):
        player = _read_save_file(BACKUP_FILE)
        if player is not None:
            print("백업에서 복구되었습니다.")
            _player_cache = player
            save_player_state(player)
            return player

    # 4순위: 새 게임
    player = create_new_game()
    _player_cache = player
    return player


def create_new_game() -> PlayerState:
    player = PlayerState(name="모험가")
    player.inventory.add_item(create_item("torch", 3))
    player.inventory.add_item(create_item("map"))
    player.inventory.add_item(create_item("small_potion", 2))
    return player


def save_player_state(player: PlayerState) -> None:
    """원자적 저장: 임시 파일에 쓴 후 교체. 이전 저장본은 백업으로 보존"""
    global _player_cache
    _player_cache = player

    tmp_file = SAVE_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(player.dict(), f, ensure_ascii=False, indent=2)

    if os.path.exists(SAVE_FILE):
        os.replace(SAVE_FILE, BACKUP_FILE)
    os.replace(tmp_file, SAVE_FILE)


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


@app.get("/api/game/jobs")
async def get_available_jobs():
    jobs = {
        "warrior": {
            "name": "전사",
            "description": "높은 힘과 방어력. 전투 최전선에 선다.",
            "strength": 15,
            "dexterity": 8,
            "intelligence": 7
        },
        "rogue": {
            "name": "도적",
            "description": "빠른 민첩성과 치명타. 암살자의 길을 간다.",
            "strength": 10,
            "dexterity": 15,
            "intelligence": 8
        },
        "mage": {
            "name": "마법사",
            "description": "강력한 마법. 지능으로 전투를 지배한다.",
            "strength": 7,
            "dexterity": 10,
            "intelligence": 16
        },
        "paladin": {
            "name": "성기사",
            "description": "균형 잡힌 능력. 정의의 기사.",
            "strength": 13,
            "dexterity": 9,
            "intelligence": 11
        },
        "ranger": {
            "name": "레인저",
            "description": "자연과 화살. 거리에서 싸우는 사냥꾼.",
            "strength": 11,
            "dexterity": 14,
            "intelligence": 9
        }
    }
    return {"jobs": jobs}


@app.post("/api/game/new")
async def new_game():
    player = create_new_game()
    save_player_state(player)
    return {"player": player.dict(), "message": "새 게임이 시작되었습니다!"}


@app.post("/api/game/select-job")
async def select_job(job: str):
    player = load_player_state()

    try:
        job_class = JobClass(job)
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 직업입니다")

    player.set_job_class(job_class)
    save_player_state(player)

    job_names = {
        "warrior": "전사",
        "rogue": "도적",
        "mage": "마법사",
        "paladin": "성기사",
        "ranger": "레인저"
    }

    return {
        "message": f"{job_names.get(job, job)} 직업을 선택했습니다!",
        "player": player.dict()
    }


# ===== 기억 관리 (3계층 메모리) =====
# 단기: recent_history 원문 -> 매 턴 AI 프롬프트에 포함
# 중기: story_summary -> 오래된 대화를 병합 요약해 보존
# 장기: PlayerState (위치, 장비, 골드, 퀘스트 등)

HISTORY_TRIGGER = 30   # 이 개수에 도달하면 요약 실행
HISTORY_KEEP = 10      # 요약 후 원문으로 유지할 최근 대화 수

_summary_in_progress = False


async def _merge_old_history_into_summary(old_messages: list):
    """오래된 대화를 기존 요약과 병합 (백그라운드 실행 - 게임 지연 없음)"""
    global _summary_in_progress
    try:
        player = load_player_state()
        new_summary = await ollama.update_summary(player.story_summary, old_messages)
        player.story_summary = new_summary
        save_player_state(player)
    finally:
        _summary_in_progress = False


def _maybe_compress_memory(player: PlayerState, background_tasks: BackgroundTasks) -> None:
    """대화가 쌓이면 오래된 부분을 잘라 백그라운드 요약으로 넘김"""
    global _summary_in_progress

    if len(player.recent_history) >= HISTORY_TRIGGER and not _summary_in_progress:
        _summary_in_progress = True
        cut = len(player.recent_history) - HISTORY_KEEP
        old_messages = player.recent_history[:cut]
        player.recent_history = player.recent_history[cut:]
        background_tasks.add_task(_merge_old_history_into_summary, old_messages)


def _handle_defeat(player: PlayerState, logs: list) -> None:
    """사망 처리: 골드 10% 손실 후 마을에서 부활"""
    enemy_name = player.current_enemy.name if player.current_enemy else "적"
    lost_gold = player.gold // 10
    player.gold -= lost_gold
    player.hp = max(1, player.max_hp // 2)
    player.location = "교차로 마을"
    player.current_enemy = None
    logs.append(f"쓰러졌다... 골드 {lost_gold}을(를) 잃고 교차로 마을에서 눈을 떴다.")
    player.add_history("시스템", f"{enemy_name}에게 패배해 교차로 마을에서 다시 눈을 떴다.")


@app.post("/api/combat/start")
async def start_combat():
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="이미 전투 중입니다")

    enemy = get_random_enemy(player.level)
    player.current_enemy = enemy
    save_player_state(player)

    return {
        "logs": [f"{enemy.name}(레벨 {enemy.level})이(가) 나타났다!"],
        "player": player.dict()
    }


@app.post("/api/combat/attack")
async def combat_attack():
    player = load_player_state()
    enemy = player.current_enemy

    if not enemy:
        raise HTTPException(status_code=400, detail="전투 중이 아닙니다")

    logs = []
    combat_over = False
    victory = False

    # 플레이어의 공격 (80% ~ 120% 편차)
    damage = max(1, int(player.get_effective_attack() * random.uniform(0.8, 1.2)) - enemy.defense)
    enemy.hp = max(0, enemy.hp - damage)
    logs.append(f"{enemy.name}에게 {damage}의 피해를 입혔다. (적 체력 {enemy.hp}/{enemy.max_hp})")

    if enemy.hp <= 0:
        # 승리 - 보상 지급
        combat_over = True
        victory = True
        player.gold += enemy.gold_reward
        logs.append(f"{enemy.name}을(를) 물리쳤다! 경험치 +{enemy.xp_reward}, 골드 +{enemy.gold_reward}")

        drop_id = roll_drop(enemy.id)
        if drop_id:
            drop_item = create_item(drop_id)
            if player.inventory.add_item(drop_item):
                logs.append(f"전리품 획득: {drop_item.name}")
            else:
                logs.append("인벤토리가 가득 차서 전리품을 놓쳤다.")

        levels_gained = player.gain_experience(enemy.xp_reward)
        if levels_gained > 0:
            logs.append(f"레벨 업! 현재 레벨 {player.level} (체력 전체 회복)")

        player.current_enemy = None
        # 전투 결과를 기억에 기록 (나레이터가 이후 이야기에 반영)
        player.add_history("시스템", f"{player.location}에서 {enemy.name}을(를) 물리쳤다.")
    else:
        # 적의 반격
        enemy_damage = player.take_damage(int(enemy.attack * random.uniform(0.8, 1.2)))
        logs.append(f"{enemy.name}의 공격! {enemy_damage}의 피해를 입었다.")

        if player.hp <= 0:
            combat_over = True
            _handle_defeat(player, logs)

    save_player_state(player)
    return {
        "logs": logs,
        "combat_over": combat_over,
        "victory": victory,
        "player": player.dict()
    }


@app.post("/api/combat/flee")
async def combat_flee():
    player = load_player_state()
    enemy = player.current_enemy

    if not enemy:
        raise HTTPException(status_code=400, detail="전투 중이 아닙니다")

    logs = []
    combat_over = False

    # 도주 확률: 민첩에 비례 (최대 90%)
    flee_chance = min(90, 40 + player.dexterity * 2)

    if random.randint(1, 100) <= flee_chance:
        combat_over = True
        player.current_enemy = None
        logs.append("무사히 도망쳤다.")
    else:
        logs.append("도망치지 못했다!")
        enemy_damage = player.take_damage(int(enemy.attack * random.uniform(0.8, 1.2)))
        logs.append(f"{enemy.name}의 공격! {enemy_damage}의 피해를 입었다.")

        if player.hp <= 0:
            combat_over = True
            _handle_defeat(player, logs)

    save_player_state(player)
    return {
        "logs": logs,
        "combat_over": combat_over,
        "victory": False,
        "player": player.dict()
    }


@app.get("/api/shop/list")
async def shop_list():
    player = load_player_state()

    stock = []
    for item_id in SHOP_STOCK:
        data = ITEMS_DB[item_id]
        stock.append({
            "id": item_id,
            "name": data["name"],
            "description": data["description"],
            "item_type": data["item_type"].value,
            "price": data["price"]
        })

    # 판매 가능한 아이템 (특수/퀘스트 아이템 제외, 판매가 = 정가의 절반)
    sellable = []
    for item in player.inventory.items:
        if item.item_type in (ItemType.SPECIAL, ItemType.QUEST_ITEM):
            continue
        sellable.append({
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "sell_price": get_item_price(item.id) // 2
        })

    return {"stock": stock, "sellable": sellable, "gold": player.gold}


@app.post("/api/shop/buy")
async def shop_buy(item_id: str):
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 상점을 이용할 수 없습니다")

    if item_id not in SHOP_STOCK:
        raise HTTPException(status_code=404, detail="상점에서 팔지 않는 아이템입니다")

    price = get_item_price(item_id)
    if player.gold < price:
        raise HTTPException(status_code=400, detail="골드가 부족합니다")

    item = create_item(item_id)
    if not player.inventory.add_item(item):
        raise HTTPException(status_code=400, detail="인벤토리가 가득 찼습니다")

    player.gold -= price
    save_player_state(player)

    return {
        "message": f"{item.name}을(를) {price} 골드에 구매했습니다",
        "player": player.dict()
    }


@app.post("/api/shop/sell")
async def shop_sell(item_id: str):
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 상점을 이용할 수 없습니다")

    item = next((i for i in player.inventory.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    if item.item_type in (ItemType.SPECIAL, ItemType.QUEST_ITEM):
        raise HTTPException(status_code=400, detail="이 아이템은 판매할 수 없습니다")

    sell_price = get_item_price(item.id) // 2
    item_name = item.name
    player.inventory.remove_item(item_id, 1)
    player.gold += sell_price
    save_player_state(player)

    return {
        "message": f"{item_name}을(를) {sell_price} 골드에 판매했습니다",
        "player": player.dict()
    }


@app.post("/api/game/action")
async def perform_action(action: PlayerAction, background_tasks: BackgroundTasks):
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 행동할 수 없습니다. 공격 또는 도망 버튼을 사용하세요.")

    narrative = await ollama.generate_narrative(player, action.action)

    special_event = await ollama.generate_special_event(player)

    # 단기 기억에 기록 (다음 턴부터 AI가 이 대화를 참조)
    player.add_history("플레이어", action.action)
    player.add_history("나레이터", narrative)
    if special_event:
        player.add_history("시스템", special_event)

    # 대화가 쌓이면 오래된 부분을 백그라운드에서 요약에 병합
    _maybe_compress_memory(player, background_tasks)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
