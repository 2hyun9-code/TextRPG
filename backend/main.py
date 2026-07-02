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
    AIResponse, GameMessage, JobClass, Enemy, Quest
)
from ollama_client import OllamaClient
from items_db import ITEMS_DB, SHOP_STOCK, create_item, get_item_price
from enemies_db import (
    ENEMY_TEMPLATES, get_random_enemy_in_range, get_templates_in_range, roll_drop,
    build_dynamic_enemy, stat_formula_xp, stat_formula_gold
)
import uuid

# AI 동적 생성 on/off (테스트 시 0으로 설정해 LLM 호출 생략)
USE_AI_GENERATION = os.getenv("TEXTRPG_AI_GEN", "1") != "0"

# 지역 정의: 이름 -> (설명, 적 레벨 범위, 휴식 가능 여부)
LOCATIONS = {
    "교차로 마을": {"description": "모험의 시작점. 여관에서 쉴 수 있다.", "min_level": 1, "max_level": 2, "can_rest": True},
    "어두운 숲": {"description": "그림자가 짙게 드리운 숲.", "min_level": 2, "max_level": 5, "can_rest": False},
    "버려진 광산": {"description": "괴물이 자리 잡은 오래된 광산.", "min_level": 5, "max_level": 8, "can_rest": False},
    "고대 유적": {"description": "잊혀진 문명의 폐허.", "min_level": 8, "max_level": 12, "can_rest": False},
    "용의 둥지": {"description": "가장 위험한 자들만 발을 들이는 곳.", "min_level": 11, "max_level": 15, "can_rest": False},
}

MAX_ACTIVE_QUESTS = 3

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
    player.stats_deaths += 1
    logs.append(f"쓰러졌다... 골드 {lost_gold}을(를) 잃고 교차로 마을에서 눈을 떴다.")
    player.add_history("시스템", f"{enemy_name}에게 패배해 교차로 마을에서 다시 눈을 떴다.")


@app.get("/api/game/locations")
async def get_locations():
    player = load_player_state()
    locations = []
    for name, info in LOCATIONS.items():
        locations.append({
            "name": name,
            "description": info["description"],
            "min_level": info["min_level"],
            "max_level": info["max_level"],
            "can_rest": info["can_rest"],
            "current": name == player.location
        })
    return {"locations": locations}


@app.post("/api/game/travel")
async def travel(location: str):
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 이동할 수 없습니다")
    if location not in LOCATIONS:
        raise HTTPException(status_code=400, detail="존재하지 않는 지역입니다")
    if player.location == location:
        raise HTTPException(status_code=400, detail="이미 그곳에 있습니다")

    player.location = location
    player.add_history("시스템", f"{location}(으)로 이동했다.")
    save_player_state(player)

    return {
        "message": f"{location}에 도착했다. {LOCATIONS[location]['description']}",
        "player": player.dict()
    }


@app.post("/api/game/rest")
async def rest_at_inn():
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 쉴 수 없습니다")
    if not LOCATIONS.get(player.location, {}).get("can_rest"):
        raise HTTPException(status_code=400, detail="이곳에는 여관이 없습니다")
    if player.hp >= player.max_hp:
        raise HTTPException(status_code=400, detail="이미 체력이 가득 찼습니다")

    cost = 10 + player.level * 5
    if player.gold < cost:
        raise HTTPException(status_code=400, detail=f"골드가 부족합니다 (필요: {cost})")

    player.gold -= cost
    player.hp = player.max_hp
    player.add_history("시스템", "여관에서 하룻밤 쉬어 체력을 모두 회복했다.")
    save_player_state(player)

    return {
        "message": f"여관에서 편안히 쉬었다. 체력이 모두 회복되었다. (-{cost} 골드)",
        "player": player.dict()
    }


def _quest_offer_for(location: str, count: int) -> dict:
    """지역 기반 처치 퀘스트 정의 (동적 몬스터도 카운트됨)"""
    loc = LOCATIONS[location]
    avg_level = (loc["min_level"] + loc["max_level"]) // 2
    return {
        "id": f"ql_{location}_{count}",
        "title": f"{location} 소탕: 몬스터 {count}마리 처치",
        "target_location": location,
        "target_count": count,
        "reward_gold": int(stat_formula_gold(avg_level) * count * 0.6),
        "reward_xp": int(stat_formula_xp(avg_level) * count * 0.4),
    }


@app.get("/api/quest/available")
async def quest_available():
    player = load_player_state()

    if player.location not in LOCATIONS:
        return {"offers": [], "active_count": len(player.active_quests), "max_active": MAX_ACTIVE_QUESTS}

    active_locations = {q.target_location for q in player.active_quests}

    offers = []
    for count in (3, 5, 8):
        offer = _quest_offer_for(player.location, count)
        offer["already_active"] = player.location in active_locations
        offers.append(offer)

    return {
        "offers": offers,
        "active_count": len(player.active_quests),
        "max_active": MAX_ACTIVE_QUESTS
    }


@app.post("/api/quest/accept")
async def quest_accept(quest_id: str):
    player = load_player_state()

    if len(player.active_quests) >= MAX_ACTIVE_QUESTS:
        raise HTTPException(status_code=400, detail=f"퀘스트는 최대 {MAX_ACTIVE_QUESTS}개까지 수락할 수 있습니다")

    # quest_id 형식: ql_<지역명>_<count>
    parts = quest_id.split("_")
    if len(parts) < 3 or parts[0] != "ql":
        raise HTTPException(status_code=400, detail="유효하지 않은 퀘스트입니다")

    try:
        count = int(parts[-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 퀘스트입니다")

    location = "_".join(parts[1:-1])
    if location not in LOCATIONS or count not in (3, 5, 8):
        raise HTTPException(status_code=400, detail="유효하지 않은 퀘스트입니다")

    if any(q.target_location == location for q in player.active_quests):
        raise HTTPException(status_code=400, detail="이미 이 지역의 퀘스트를 진행 중입니다")

    offer = _quest_offer_for(location, count)
    quest = Quest(
        id=offer["id"],
        title=offer["title"],
        target_location=location,
        target_count=count,
        reward_gold=offer["reward_gold"],
        reward_xp=offer["reward_xp"],
    )
    player.active_quests.append(quest)
    player.add_history("시스템", f"퀘스트 수락: {quest.title}")
    save_player_state(player)

    return {
        "message": f"퀘스트 수락: {quest.title}",
        "player": player.dict()
    }


def _update_quest_progress(player: PlayerState, enemy_id: str, logs: list) -> None:
    """적 처치 시 퀘스트 진행/완료 처리 (지역 기반 + 구버전 몬스터 지정 호환)"""
    completed = []
    for q in player.active_quests:
        location_match = q.target_location and q.target_location == player.location
        enemy_match = q.target_enemy_id and q.target_enemy_id == enemy_id
        if not (location_match or enemy_match):
            continue
        q.progress += 1
        if q.progress >= q.target_count:
            player.gold += q.reward_gold
            levels = player.gain_experience(q.reward_xp)
            logs.append(f"퀘스트 완료: {q.title}! 보상 골드 +{q.reward_gold}, 경험치 +{q.reward_xp}")
            if levels > 0:
                logs.append(f"레벨 업! 현재 레벨 {player.level} (체력 전체 회복)")
            player.stats_quests_completed += 1
            player.add_history("시스템", f"퀘스트 완료: {q.title}")
            completed.append(q.id)
        else:
            logs.append(f"퀘스트 진행: {q.title} ({q.progress}/{q.target_count})")

    if completed:
        player.active_quests = [q for q in player.active_quests if q.id not in completed]


@app.post("/api/combat/start")
async def start_combat():
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="이미 전투 중입니다")

    loc = LOCATIONS.get(player.location, {"min_level": 1, "max_level": 3})
    logs = []

    # AI가 이야기 맥락에 맞는 몬스터를 창작 (스탯은 코드가 밸런스 보장)
    concept = None
    if USE_AI_GENERATION:
        concept = await ollama.generate_enemy_concept(player)

    if concept:
        level = random.randint(loc["min_level"], loc["max_level"])
        enemy = build_dynamic_enemy(concept["name"], level)
        logs.append(f"{enemy.name}(레벨 {enemy.level})이(가) 나타났다!")
        if concept.get("description"):
            logs.append(concept["description"])
    else:
        # AI 실패 시 고전 몬스터 폴백
        enemy = get_random_enemy_in_range(loc["min_level"], loc["max_level"])
        logs.append(f"{enemy.name}(레벨 {enemy.level})이(가) 나타났다!")

    player.current_enemy = enemy
    save_player_state(player)

    return {
        "logs": logs,
        "player": player.dict()
    }


def _potion_for_level(level: int) -> str:
    if level >= 10:
        return "large_potion"
    if level >= 5:
        return "medium_potion"
    return "small_potion"


async def _roll_dynamic_drop(player: PlayerState, enemy) -> Optional[Item]:
    """동적 몬스터의 전리품: 물약(고정 DB) 또는 AI 창작 장비(코드 스탯)"""
    roll = random.random()

    if roll < 0.30:
        # 물약 드롭
        return create_item(_potion_for_level(enemy.level))

    if roll < 0.45:
        # AI 창작 장비 드롭
        kind = random.choice(["weapon", "armor"])
        concept = None
        if USE_AI_GENERATION:
            concept = await ollama.generate_item_concept(player, kind)

        level = enemy.level
        if kind == "weapon":
            bonus = max(2, int(level * 1.1) + random.randint(-1, 2))
            effect = {"attack_bonus": bonus}
            price = int(bonus * (7 + bonus * 1.3))
            fallback_name = f"이름 모를 무기 (레벨 {level})"
            item_type = ItemType.WEAPON
        else:
            bonus = max(1, int(level * 0.9) + random.randint(-1, 1))
            effect = {"defense_bonus": bonus}
            price = int(bonus * (20 + bonus * 2.6))
            fallback_name = f"이름 모를 방어구 (레벨 {level})"
            item_type = ItemType.ARMOR

        name = concept["name"] if concept else fallback_name
        description = concept.get("description", "") if concept else "정체를 알 수 없는 전리품."

        return Item(
            id=f"dyn_{kind}_{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            item_type=item_type,
            effect=effect,
            quantity=1,
            price=price
        )

    return None


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

        # 전리품: 동적 몬스터는 AI 창작 장비/물약, 고전 몬스터는 드롭 테이블
        if enemy.id.startswith("dyn_"):
            drop_item = await _roll_dynamic_drop(player, enemy)
        else:
            drop_id = roll_drop(enemy.id)
            drop_item = create_item(drop_id) if drop_id else None

        if drop_item:
            if player.inventory.add_item(drop_item):
                logs.append(f"전리품 획득: {drop_item.name}")
                if drop_item.description and drop_item.id.startswith("dyn_"):
                    logs.append(drop_item.description)
            else:
                logs.append("인벤토리가 가득 차서 전리품을 놓쳤다.")

        levels_gained = player.gain_experience(enemy.xp_reward)
        if levels_gained > 0:
            logs.append(f"레벨 업! 현재 레벨 {player.level} (체력 전체 회복)")

        player.current_enemy = None
        player.stats_kills += 1
        # 퀘스트 진행 갱신
        _update_quest_progress(player, enemy.id, logs)
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
            "sell_price": (item.price or get_item_price(item.id)) // 2
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

    sell_price = (item.price or get_item_price(item.id)) // 2
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
