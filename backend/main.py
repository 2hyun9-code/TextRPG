from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from models import (
    PlayerState, PlayerAction, Item, ItemType, Equipment, Inventory,
    AIResponse, GameMessage, JobClass, Enemy, Quest
)
from ollama_client import OllamaClient
from items_db import ITEMS_DB, SHOP_STOCK, create_item, get_item_price
from story import get_prologue, get_seed_summary, JOB_NAMES
from skills_db import get_skill
from enemies_db import (
    ENEMY_TEMPLATES, get_random_enemy_in_range, get_templates_in_range, roll_drop,
    build_dynamic_enemy, stat_formula_xp, stat_formula_gold
)
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("textrpg.main")

# AI 동적 생성 on/off (테스트 시 0으로 설정해 LLM 호출 생략)
USE_AI_GENERATION = os.getenv("TEXTRPG_AI_GEN", "1") != "0"

# 지역 정의: 이야기 배경 역할 (적 강함은 지역이 아닌 플레이어 레벨에 맞춰 결정됨)
LOCATIONS = {
    "교차로 마을": {"description": "모험의 시작점. 여관에서 쉴 수 있다.", "can_rest": True},
    "어두운 숲": {"description": "그림자가 짙게 드리운 숲.", "can_rest": False},
    "버려진 광산": {"description": "괴물이 자리 잡은 오래된 광산.", "can_rest": False},
    "고대 유적": {"description": "잊혀진 문명의 폐허.", "can_rest": False},
    "용의 둥지": {"description": "가장 위험한 자들만 발을 들이는 곳.", "can_rest": False},
}

MAX_ACTIVE_QUESTS = 5        # 지역 5곳 x 지역당 1개 + 보스/탐험 병행 가능
COMPLETED_QUESTS_CAP = 20    # 완료 기록 보관 개수 (저장 파일 비대화 방지)

# 적 레벨 = 플레이어 레벨 기준 이 범위 내에서 결정
ENEMY_LEVEL_MIN_OFFSET = -1
ENEMY_LEVEL_MAX_OFFSET = 2

BOSS_CHANCE = 0.10        # 사냥 시 보스 조우 확률
BOSS_LEVEL_OFFSET = 2     # 보스 레벨 = 플레이어 레벨 + 2
BOSS_MIN_PLAYER_LEVEL = 3  # 이 레벨 미만에서는 보스 미등장 (초반 보호)

# 행동 한 번에 AI를 여러 번 호출하면(서사+퀘스트훅+이벤트추출) 느린 하드웨어에서
# 응답이 크게 늘어지므로, 두 부가 기능은 매 턴이 아닌 확률적으로만 실행한다.
SPECIAL_EVENT_CHANCE = 0.20  # 지도 소지 시 퀘스트 훅이 뜰 확률
STORY_EVENT_CHANCE = 0.40    # 서사 속 골드/체력/아이템 변화를 반영 시도할 확률

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


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/frontend/")

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
            player = PlayerState(**data)
            # 마나 도입 이전 세이브 마이그레이션
            if "max_mp" not in data and player.job_selected:
                player.apply_mp_migration()
            return player
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
    global _summary_in_progress

    # 모델을 미리 로드해 첫 사용자 요청의 지연을 없앤다.
    # 프리워밍 실패(Ollama 미실행 등)해도 서버 시작은 막지 않는다.
    if USE_AI_GENERATION:
        await ollama.warmup()

    # 이전 실행에서 중단된 요약이 있으면 재시도 (재시작 기억 유실 방지)
    if os.path.exists(SAVE_FILE):
        player = load_player_state()
        if player.pending_summary and not _summary_in_progress:
            logger.info("미완료 요약 발견 (%d개 메시지) - 백그라운드 재시도", len(player.pending_summary))
            _summary_in_progress = True
            asyncio.create_task(_merge_pending_summary())


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


# ===== 저장 슬롯 (3개) =====

SAVE_SLOTS = 3


def _slot_path(slot: int) -> str:
    return f"save_slot_{slot}.json"


def _validate_slot(slot: int) -> None:
    if slot < 1 or slot > SAVE_SLOTS:
        raise HTTPException(status_code=400, detail=f"슬롯은 1~{SAVE_SLOTS} 사이여야 합니다")


@app.get("/api/saves")
async def list_saves():
    """저장 슬롯 목록 (요약 정보만)"""
    slots = []
    for slot in range(1, SAVE_SLOTS + 1):
        path = _slot_path(slot)
        info = {"slot": slot, "exists": False}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                info.update({
                    "exists": True,
                    "name": data.get("name", "?"),
                    "level": data.get("level", 1),
                    "job": JOB_NAMES.get(data.get("job_class", ""), data.get("job_class", "?")),
                    "location": data.get("location", "?"),
                    "saved_at": data.get("_saved_at", ""),
                })
            except (json.JSONDecodeError, OSError):
                info["corrupted"] = True
        slots.append(info)
    return {"slots": slots}


@app.post("/api/saves/save")
async def save_to_slot(slot: int):
    """현재 진행을 슬롯에 저장 (기존 슬롯 내용은 덮어씀)"""
    _validate_slot(slot)
    player = load_player_state()

    data = player.dict()
    data["_saved_at"] = datetime.now().isoformat(timespec="seconds")

    tmp = _slot_path(slot) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _slot_path(slot))

    return {"message": f"슬롯 {slot}에 저장했습니다", "slot": slot}


@app.post("/api/saves/load")
async def load_from_slot(slot: int):
    """슬롯의 진행을 불러와 현재 게임으로 교체"""
    _validate_slot(slot)
    path = _slot_path(slot)

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="빈 슬롯입니다")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.pop("_saved_at", None)
        player = PlayerState(**data)
    except (json.JSONDecodeError, ValueError, OSError):
        raise HTTPException(status_code=400, detail="슬롯 데이터가 손상되었습니다")

    save_player_state(player)
    return {
        "message": f"슬롯 {slot}을 불러왔습니다",
        "player": player.dict()
    }


@app.post("/api/game/select-job")
async def select_job(job: str):
    player = load_player_state()

    try:
        job_class = JobClass(job)
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 직업입니다")

    player.set_job_class(job_class)

    # 고정 프롤로그: AI의 초기 기억에 서장을 심는다.
    # 나레이터는 이 전제에서 이야기를 시작하고, 이후 플레이어의
    # 선택이 요약에 병합되며 매번 다른 이야기로 갈라진다.
    prologue = get_prologue(job)
    player.story_summary = get_seed_summary(player.name, job)
    player.add_history("나레이터", prologue[2])  # 촌장의 부탁 장면을 단기 기억에도 기록

    save_player_state(player)

    return {
        "message": f"{JOB_NAMES.get(job, job)} 직업을 선택했습니다!",
        "prologue": prologue,
        "player": player.dict()
    }


# ===== 기억 관리 (3계층 메모리) =====
# 단기: recent_history 원문 -> 매 턴 AI 프롬프트에 포함
# 중기: story_summary -> 오래된 대화를 병합 요약해 보존
# 장기: PlayerState (위치, 장비, 골드, 퀘스트 등)

HISTORY_TRIGGER = 60           # 이 개수에 도달하면 요약 실행 (요약은 백그라운드라 응답 속도에 영향 없음)
HISTORY_KEEP = 20              # 요약 후 원문으로 유지할 최근 대화 수 (매 턴 프롬프트에 포함되는 개수와 일치)
MAX_HISTORY_HARD_LIMIT = 300   # 절대 상한: 요약 시스템이 고장 나도 이 이상 쌓이지 않음

_summary_in_progress = False


async def _merge_pending_summary():
    """대기 중인 오래된 대화를 기존 요약과 병합 (백그라운드 실행 - 게임 지연 없음)

    잘라낸 대화는 pending_summary로 세이브 파일에 먼저 영속화되어 있으므로,
    요약 도중 서버가 재시작돼도 유실되지 않는다 (startup에서 재시도).
    """
    global _summary_in_progress
    try:
        player = load_player_state()
        if not player.pending_summary:
            return
        new_summary = await ollama.update_summary(player.story_summary, player.pending_summary)
        player.story_summary = new_summary
        player.pending_summary = []  # 병합 성공 후에만 비움
        save_player_state(player)
    except Exception as e:
        # pending은 그대로 유지 -> 다음 트리거나 재시작 시 자동 재시도
        logger.error("요약 병합 실패 (대기 목록 유지, 재시도 예정): %s", e)
    finally:
        _summary_in_progress = False


async def force_compress_now() -> dict:
    """매일 자정(00:00) 강제 압축: 트리거 개수(60)에 못 미쳐도 그날 대화를 전부 요약에 반영한다.

    HISTORY_TRIGGER를 기다리지 않고 즉시 병합하므로, 활동이 적은 날에도
    recent_history가 다음날로 무한정 누적되지 않고 매일 정리된다.
    운영 서버에서는 systemd 타이머가 자정에 이 엔드포인트를 호출한다.
    """
    global _summary_in_progress

    if _summary_in_progress:
        return {"trimmed": 0, "merged": 0, "skipped": "이미 압축이 진행 중입니다"}

    _summary_in_progress = True
    try:
        player = load_player_state()

        trimmed = 0
        if len(player.recent_history) > HISTORY_KEEP:
            cut = len(player.recent_history) - HISTORY_KEEP
            player.pending_summary.extend(player.recent_history[:cut])
            player.recent_history = player.recent_history[cut:]
            trimmed = cut

        merged = len(player.pending_summary)
        if merged > 0:
            new_summary = await ollama.update_summary(player.story_summary, player.pending_summary)
            player.story_summary = new_summary
            player.pending_summary = []

        save_player_state(player)
        logger.info("자정 강제 압축 완료: 정리 %d개, 병합 %d개", trimmed, merged)
        return {"trimmed": trimmed, "merged": merged}
    finally:
        _summary_in_progress = False


def _maybe_compress_memory(player: PlayerState, background_tasks: BackgroundTasks) -> None:
    """대화가 쌓이면 오래된 부분을 잘라 백그라운드 요약으로 넘김"""
    global _summary_in_progress

    # 최후의 안전밸브: 요약 시스템이 어떤 이유로든 멈춰도 메모리 고갈은 막는다.
    # 이 시점의 오래된 대화는 요약 없이 폐기된다 (메모리 보호 우선).
    if len(player.recent_history) >= MAX_HISTORY_HARD_LIMIT:
        dropped = len(player.recent_history) - HISTORY_KEEP
        player.recent_history = player.recent_history[-HISTORY_KEEP:]
        logger.warning("히스토리 하드 상한 도달 - 오래된 대화 %d개 강제 정리", dropped)
        return

    if len(player.recent_history) >= HISTORY_TRIGGER and not _summary_in_progress:
        _summary_in_progress = True
        cut = len(player.recent_history) - HISTORY_KEEP
        # 잘라낸 대화를 pending에 영속화 (호출자가 곧바로 save하므로 파일에 기록됨)
        player.pending_summary.extend(player.recent_history[:cut])
        player.recent_history = player.recent_history[cut:]
        background_tasks.add_task(_merge_pending_summary)


def _handle_defeat(player: PlayerState, logs: list) -> None:
    """사망 처리: 골드 10% 손실 후 마을에서 부활"""
    enemy_name = player.current_enemy.name if player.current_enemy else "적"
    lost_gold = player.gold // 10
    player.gold -= lost_gold
    player.hp = max(1, player.max_hp // 2)
    player.location = "교차로 마을"
    player.current_enemy = None
    player.stats_deaths += 1
    player.clear_status()
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

    # 탐험 퀘스트 진행 (완료 시 보상 지급까지 처리됨)
    quest_logs = []
    _update_explore_progress(player, quest_logs)

    save_player_state(player)

    return {
        "message": f"{location}에 도착했다. {LOCATIONS[location]['description']}",
        "logs": quest_logs,
        "player": player.dict()
    }


@app.post("/api/game/rest")
async def rest_at_inn():
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 쉴 수 없습니다")
    if not LOCATIONS.get(player.location, {}).get("can_rest"):
        raise HTTPException(status_code=400, detail="이곳에는 여관이 없습니다")
    if player.hp >= player.max_hp and player.mp >= player.max_mp:
        raise HTTPException(status_code=400, detail="이미 체력과 정신력이 가득 찼습니다")

    cost = 10 + player.level * 5
    if player.gold < cost:
        raise HTTPException(status_code=400, detail=f"골드가 부족합니다 (필요: {cost})")

    player.gold -= cost
    player.hp = player.max_hp
    player.mp = player.max_mp
    player.clear_status()
    player.add_history("시스템", "여관에서 하룻밤 쉬어 체력과 정신력을 모두 회복했다.")
    save_player_state(player)

    return {
        "message": f"여관에서 편안히 쉬었다. 체력과 정신력이 모두 회복되었다. (-{cost} 골드)",
        "player": player.dict()
    }


def _quest_offer_for(location: str, count: int, player_level: int) -> dict:
    """지역 기반 처치 퀘스트 정의 (보상은 플레이어 레벨에 비례)"""
    return {
        "id": f"ql_{location}_{count}",
        "title": f"{location} 소탕: 몬스터 {count}마리 처치",
        "quest_type": "hunt",
        "target_location": location,
        "target_count": count,
        "reward_gold": int(stat_formula_gold(player_level) * count * 0.6),
        "reward_xp": int(stat_formula_xp(player_level) * count * 0.4),
    }


def _boss_quest_offer(player_level: int) -> dict:
    """보스 토벌 퀘스트: 어느 지역이든 보스 1마리 처치"""
    return {
        "id": "qb_1",
        "title": "보스 토벌: 보스 1마리 처치",
        "quest_type": "boss",
        "target_count": 1,
        "reward_gold": int(stat_formula_gold(player_level) * 2.5),
        "reward_xp": int(stat_formula_xp(player_level) * 2.0),
    }


def _explore_quest_offer(player_level: int) -> dict:
    """탐험 퀘스트: 수락 후 다른 지역 2곳 방문"""
    return {
        "id": "qe_2",
        "title": "미지의 발걸음: 다른 지역 2곳 방문",
        "quest_type": "explore",
        "target_count": 2,
        "reward_gold": int(stat_formula_gold(player_level) * 1.2),
        "reward_xp": int(stat_formula_xp(player_level) * 1.0),
    }


@app.get("/api/quest/available")
async def quest_available():
    player = load_player_state()

    if player.location not in LOCATIONS:
        return {"offers": [], "active_count": len(player.active_quests), "max_active": MAX_ACTIVE_QUESTS}

    active_locations = {q.target_location for q in player.active_quests if q.quest_type == "hunt"}
    active_types = {q.quest_type for q in player.active_quests}

    offers = []
    for count in (3, 5, 8):
        offer = _quest_offer_for(player.location, count, player.level)
        offer["already_active"] = player.location in active_locations
        offers.append(offer)

    boss_offer = _boss_quest_offer(player.level)
    boss_offer["already_active"] = "boss" in active_types
    offers.append(boss_offer)

    explore_offer = _explore_quest_offer(player.level)
    explore_offer["already_active"] = "explore" in active_types
    offers.append(explore_offer)

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

    if quest_id == "qb_1":
        # 보스 토벌
        if any(q.quest_type == "boss" for q in player.active_quests):
            raise HTTPException(status_code=400, detail="이미 보스 토벌 퀘스트를 진행 중입니다")
        offer = _boss_quest_offer(player.level)
        quest = Quest(
            id=offer["id"], title=offer["title"], quest_type="boss",
            target_count=offer["target_count"],
            reward_gold=offer["reward_gold"], reward_xp=offer["reward_xp"],
        )
    elif quest_id == "qe_2":
        # 탐험: 수락한 지역은 방문 목록에 미리 넣어 "다른" 지역만 카운트
        if any(q.quest_type == "explore" for q in player.active_quests):
            raise HTTPException(status_code=400, detail="이미 탐험 퀘스트를 진행 중입니다")
        offer = _explore_quest_offer(player.level)
        quest = Quest(
            id=offer["id"], title=offer["title"], quest_type="explore",
            target_count=offer["target_count"],
            reward_gold=offer["reward_gold"], reward_xp=offer["reward_xp"],
            visited_locations=[player.location],
        )
    else:
        # 처치 퀘스트: ql_<지역명>_<count>
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

        if any(q.quest_type == "hunt" and q.target_location == location for q in player.active_quests):
            raise HTTPException(status_code=400, detail="이미 이 지역의 퀘스트를 진행 중입니다")

        offer = _quest_offer_for(location, count, player.level)
        quest = Quest(
            id=offer["id"], title=offer["title"], quest_type="hunt",
            target_location=location, target_count=count,
            reward_gold=offer["reward_gold"], reward_xp=offer["reward_xp"],
        )

    player.active_quests.append(quest)
    player.add_history("시스템", f"퀘스트 수락: {quest.title}")
    save_player_state(player)

    return {
        "message": f"퀘스트 수락: {quest.title}",
        "player": player.dict()
    }


def _complete_quest(player: PlayerState, q: Quest, logs: list) -> None:
    """퀘스트 완료 공통 처리: 보상 지급 + 완료 기록 저장"""
    player.gold += q.reward_gold
    levels = player.gain_experience(q.reward_xp)
    logs.append(f"퀘스트 완료: {q.title}! 보상 골드 +{q.reward_gold}, 경험치 +{q.reward_xp}")
    if levels > 0:
        logs.append(f"레벨 업! 현재 레벨 {player.level} (체력 전체 회복)")

    player.stats_quests_completed += 1
    player.completed_quests.append({
        "id": q.id,
        "title": q.title,
        "quest_type": q.quest_type,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "reward_gold": q.reward_gold,
        "reward_xp": q.reward_xp,
    })
    if len(player.completed_quests) > COMPLETED_QUESTS_CAP:
        player.completed_quests = player.completed_quests[-COMPLETED_QUESTS_CAP:]

    player.add_history("시스템", f"퀘스트 완료: {q.title}")


def _update_quest_progress(player: PlayerState, enemy_id: str, logs: list) -> None:
    """적 처치 시 퀘스트 진행/완료 처리 (처치/보스 + 구버전 몬스터 지정 호환)"""
    is_boss_kill = enemy_id.startswith("boss_")
    completed = []
    for q in player.active_quests:
        if q.quest_type == "boss":
            if not is_boss_kill:
                continue
        elif q.quest_type == "explore":
            continue  # 탐험은 이동 시 진행
        else:
            location_match = q.target_location and q.target_location == player.location
            enemy_match = q.target_enemy_id and q.target_enemy_id == enemy_id
            if not (location_match or enemy_match):
                continue

        q.progress += 1
        if q.progress >= q.target_count:
            _complete_quest(player, q, logs)
            completed.append(q.id)
        else:
            logs.append(f"퀘스트 진행: {q.title} ({q.progress}/{q.target_count})")

    if completed:
        player.active_quests = [q for q in player.active_quests if q.id not in completed]


def _update_explore_progress(player: PlayerState, logs: list) -> None:
    """지역 이동 시 탐험 퀘스트 진행/완료 처리"""
    completed = []
    for q in player.active_quests:
        if q.quest_type != "explore":
            continue
        if player.location in q.visited_locations:
            continue
        q.visited_locations.append(player.location)
        q.progress += 1
        if q.progress >= q.target_count:
            _complete_quest(player, q, logs)
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

    logs = []
    is_boss = player.level >= BOSS_MIN_PLAYER_LEVEL and random.random() < BOSS_CHANCE

    # 적 레벨은 항상 플레이어 레벨 기준 범위 내에서 결정
    if is_boss:
        level = player.level + BOSS_LEVEL_OFFSET
    else:
        level = max(1, player.level + random.randint(ENEMY_LEVEL_MIN_OFFSET, ENEMY_LEVEL_MAX_OFFSET))

    # AI가 이야기 맥락에 맞는 몬스터를 창작 (스탯은 코드가 밸런스 보장)
    concept = None
    if USE_AI_GENERATION:
        concept = await ollama.generate_enemy_concept(player, boss=is_boss)

    if concept:
        name = concept["name"]
        description = concept.get("description", "")
    else:
        # AI 실패 시 폴백 이름
        name = "이름 없는 공포" if is_boss else get_random_enemy_in_range(max(1, level - 1), level + 1).name
        description = ""

    enemy = build_dynamic_enemy(name, level, boss=is_boss)

    if is_boss:
        logs.append(f"[보스] {enemy.name}(레벨 {enemy.level})이(가) 나타났다!")
        logs.append("압도적인 존재감이 주변을 짓누른다.")
    else:
        logs.append(f"{enemy.name}(레벨 {enemy.level})이(가) 나타났다!")

    if description:
        logs.append(description)

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


async def _roll_dynamic_drop(player: PlayerState, enemy, guaranteed: bool = False) -> Optional[Item]:
    """동적 몬스터의 전리품: 물약(고정 DB) 또는 AI 창작 장비(코드 스탯)

    guaranteed=True (보스): 반드시 장비 드롭 + 능력치 한 단계 상승
    """
    roll = random.random()

    if not guaranteed and roll < 0.30:
        # 물약 드롭
        return create_item(_potion_for_level(enemy.level))

    if guaranteed or roll < 0.45:
        # AI 창작 장비 드롭
        kind = random.choice(["weapon", "armor"])
        concept = None
        if USE_AI_GENERATION:
            concept = await ollama.generate_item_concept(player, kind)

        level = enemy.level + (2 if guaranteed else 0)
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


async def _handle_victory(player: PlayerState, enemy, logs: list) -> None:
    """전투 승리 공통 처리: 보상, 전리품, 경험치, 퀘스트, 기억"""
    player.gold += enemy.gold_reward
    logs.append(f"{enemy.name}을(를) 물리쳤다! 경험치 +{enemy.xp_reward}, 골드 +{enemy.gold_reward}")

    # 전리품: 보스는 확정 장비, 동적 몬스터는 AI 창작 장비/물약, 고전 몬스터는 드롭 테이블
    if enemy.id.startswith("boss_"):
        drop_item = await _roll_dynamic_drop(player, enemy, guaranteed=True)
    elif enemy.id.startswith("dyn_"):
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
            # 인벤토리 가득 -> 판매가만큼 골드로 대체 보상 (아이템 손실 방지)
            gold_comp = max(drop_item.price // 2, 5)
            player.gold += gold_comp
            logs.append(f"인벤토리가 가득 차서 {drop_item.name} 대신 골드 {gold_comp}을(를) 획득했다.")

    levels_gained = player.gain_experience(enemy.xp_reward)
    if levels_gained > 0:
        logs.append(f"레벨 업! 현재 레벨 {player.level} (체력/정신력 전체 회복)")

    player.current_enemy = None
    player.stats_kills += 1
    player.clear_status()  # 전투 종료 시 상태 이상 해제
    # 퀘스트 진행 갱신
    _update_quest_progress(player, enemy.id, logs)
    # 전투 결과를 기억에 기록 (나레이터가 이후 이야기에 반영)
    player.add_history("시스템", f"{player.location}에서 {enemy.name}을(를) 물리쳤다.")


def _tick_status_effects(player: PlayerState, logs: list) -> bool:
    """턴 시작 시 상태 이상 처리. 기절로 행동 불가면 True 반환"""
    stunned = False
    remaining = []
    for e in player.status_effects:
        if e["type"] == "poison":
            poison_dmg = max(1, player.level * 2)
            player.hp = max(0, player.hp - poison_dmg)
            logs.append(f"독이 몸을 파고든다... {poison_dmg}의 피해. (남은 {e['turns'] - 1}턴)")
        elif e["type"] == "stun":
            stunned = True
            logs.append("기절해서 움직일 수 없다!")
        e["turns"] -= 1
        if e["turns"] > 0:
            remaining.append(e)
    player.status_effects = remaining
    return stunned


def _enemy_counterattack(player: PlayerState, enemy, logs: list) -> None:
    """적의 반격 + 상태 이상 부여 확률"""
    enemy_damage = player.take_damage(int(enemy.attack * random.uniform(0.9, 1.1)))
    logs.append(f"{enemy.name}의 공격! {enemy_damage}의 피해를 입었다.")

    if player.hp <= 0:
        return

    # 상태 이상 부여: 보스는 기절(20%), 일반 몬스터는 중독(12%)
    if enemy.id.startswith("boss_"):
        if random.random() < 0.20 and not player.has_status("stun"):
            player.add_status("stun", 1)
            logs.append(f"{enemy.name}의 일격에 정신이 아득해진다... [기절 1턴]")
    elif random.random() < 0.12 and not player.has_status("poison"):
        player.add_status("poison", 3)
        logs.append(f"{enemy.name}의 공격에 독이 스며든다... [중독 3턴]")


async def _combat_turn(player: PlayerState, enemy, damage: int, logs: list) -> dict:
    """공격/스킬 공통 전투 턴 처리: 피해 적용 -> 승리 또는 반격/패배"""
    combat_over = False
    victory = False

    enemy.hp = max(0, enemy.hp - damage)

    if enemy.hp <= 0:
        combat_over = True
        victory = True
        await _handle_victory(player, enemy, logs)
    else:
        _enemy_counterattack(player, enemy, logs)
        if player.hp <= 0:
            combat_over = True
            player.clear_status()
            _handle_defeat(player, logs)

    save_player_state(player)
    return {
        "logs": logs,
        "combat_over": combat_over,
        "victory": victory,
        "player": player.dict()
    }


@app.post("/api/combat/attack")
async def combat_attack():
    player = load_player_state()
    enemy = player.current_enemy

    if not enemy:
        raise HTTPException(status_code=400, detail="전투 중이 아닙니다")

    logs = []

    # 상태 이상 처리 (중독 피해, 기절 시 행동 불가)
    stunned = _tick_status_effects(player, logs)
    if player.hp <= 0:
        player.clear_status()
        _handle_defeat(player, logs)
        save_player_state(player)
        return {"logs": logs, "combat_over": True, "victory": False, "player": player.dict()}
    if stunned:
        _enemy_counterattack(player, enemy, logs)
        combat_over = player.hp <= 0
        if combat_over:
            player.clear_status()
            _handle_defeat(player, logs)
        save_player_state(player)
        return {"logs": logs, "combat_over": combat_over, "victory": False, "player": player.dict()}

    # 플레이어의 공격 (90% ~ 110% 편차 - 예측 가능한 전투)
    damage = max(1, int(player.get_effective_attack() * random.uniform(0.9, 1.1)) - enemy.defense)
    logs.append(f"{enemy.name}에게 {damage}의 피해를 입혔다. (적 체력 {max(0, enemy.hp - damage)}/{enemy.max_hp})")

    return await _combat_turn(player, enemy, damage, logs)


@app.post("/api/combat/skill")
async def combat_skill():
    player = load_player_state()
    enemy = player.current_enemy

    if not enemy:
        raise HTTPException(status_code=400, detail="전투 중이 아닙니다")

    skill = get_skill(player.job_class.value)
    if player.mp < skill["mp_cost"]:
        raise HTTPException(status_code=400, detail=f"정신력이 부족합니다 (필요: {skill['mp_cost']})")

    logs = []

    stunned = _tick_status_effects(player, logs)
    if player.hp <= 0:
        player.clear_status()
        _handle_defeat(player, logs)
        save_player_state(player)
        return {"logs": logs, "combat_over": True, "victory": False, "player": player.dict()}
    if stunned:
        _enemy_counterattack(player, enemy, logs)
        combat_over = player.hp <= 0
        if combat_over:
            player.clear_status()
            _handle_defeat(player, logs)
        save_player_state(player)
        return {"logs": logs, "combat_over": combat_over, "victory": False, "player": player.dict()}

    player.mp -= skill["mp_cost"]

    # 스킬 피해 계산: 유효 공격 x 배율 + 지능 계수, 방어 무시 옵션
    base = player.get_effective_attack() * skill["damage_mult"] + player.intelligence * skill["int_scale"]
    enemy_def = 0 if skill["ignore_defense"] else enemy.defense
    damage = max(1, int(base * random.uniform(0.9, 1.1)) - enemy_def)
    logs.append(f"[{skill['name']}] {enemy.name}에게 {damage}의 피해! (적 체력 {max(0, enemy.hp - damage)}/{enemy.max_hp}, 정신력 -{skill['mp_cost']})")

    if skill["self_heal_int"] > 0:
        heal_amount = player.intelligence * skill["self_heal_int"]
        player.heal(heal_amount)
        logs.append(f"빛의 가호로 체력을 {heal_amount} 회복했다.")

    return await _combat_turn(player, enemy, damage, logs)


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
        player.clear_status()
        logs.append("무사히 도망쳤다.")
    else:
        logs.append("도망치지 못했다!")
        _enemy_counterattack(player, enemy, logs)

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


def _sell_price_of(item: Item) -> int:
    """판매가 계산: 아이템 가격 -> DB 가격 -> 효과 기반 추정 순서로 폴백, 최소 1골드"""
    price = item.price or get_item_price(item.id)
    if price <= 0:
        # 가격 정보가 전혀 없으면 효과 수치로 추정
        effect = item.effect or {}
        price = (
            effect.get("attack_bonus", 0) * 15
            + effect.get("defense_bonus", 0) * 25
            + effect.get("heal", 0)
        )
    return max(1, price // 2)


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
            "sell_price": _sell_price_of(item)
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

    sell_price = _sell_price_of(item)
    item_name = item.name
    player.inventory.remove_item(item_id, 1)
    player.gold += sell_price
    save_player_state(player)

    return {
        "message": f"{item_name}을(를) {sell_price} 골드에 판매했습니다",
        "player": player.dict()
    }


async def _apply_story_events(player: PlayerState, narrative: str) -> list:
    """서사에서 추출한 상태 변화를 검증/제한 후 적용. 적용 로그 반환

    AI는 제안만 하고 코드가 범위를 강제한다:
    - 골드: 레벨 비례 상한 (파밍 방지)
    - 체력: 레벨 비례 상한, 사망 없음 (최소 1)
    - 아이템: 인벤토리 여유 있을 때만, 스탯은 코드가 결정 (일반 몬스터 전리품보다 약간 약함)
    """
    events = await ollama.extract_story_events(narrative)
    if not events:
        return []

    logs = []

    gold_cap_gain = 10 + player.level * 2
    gold_cap_loss = 15 + player.level * 3
    gold = max(-gold_cap_loss, min(gold_cap_gain, events["gold"]))
    if gold > 0:
        player.gold += gold
        logs.append(f"골드 {gold}을(를) 얻었다. (소지 {player.gold})")
    elif gold < 0:
        actual = min(-gold, player.gold)
        player.gold -= actual
        if actual > 0:
            logs.append(f"골드 {actual}을(를) 잃었다. (소지 {player.gold})")

    hp_cap = player.level * 5
    hp = max(-hp_cap, min(hp_cap, events["hp"]))
    if hp > 0:
        player.heal(hp)
        logs.append(f"체력을 {hp} 회복했다. ({player.hp}/{player.max_hp})")
    elif hp < 0:
        player.hp = max(1, player.hp + hp)  # 서사로는 죽지 않음
        logs.append(f"체력이 {-hp} 줄었다. ({player.hp}/{player.max_hp})")

    if events["item_name"] and len(events["item_name"]) <= 24:
        kind = events["item_kind"]
        item = None
        if kind == "potion":
            item = create_item(_potion_for_level(player.level))
        elif kind in ("weapon", "armor"):
            level = max(1, int(player.level * 0.7))  # 전투 전리품보다 약간 약하게
            if kind == "weapon":
                bonus = max(1, int(level * 1.1))
                effect = {"attack_bonus": bonus}
                price = int(bonus * (7 + bonus * 1.3))
                item_type = ItemType.WEAPON
            else:
                bonus = max(1, int(level * 0.9))
                effect = {"defense_bonus": bonus}
                price = int(bonus * (20 + bonus * 2.6))
                item_type = ItemType.ARMOR
            item = Item(
                id=f"dyn_{kind}_{uuid.uuid4().hex[:8]}",
                name=events["item_name"],
                description="이야기 속에서 발견한 물건.",
                item_type=item_type,
                effect=effect,
                quantity=1,
                price=price
            )

        if item and player.inventory.add_item(item):
            logs.append(f"획득: {item.name}")

    if logs:
        player.add_history("시스템", " / ".join(logs))

    return logs


@app.post("/api/game/action")
async def perform_action(action: PlayerAction, background_tasks: BackgroundTasks):
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 행동할 수 없습니다. 공격 또는 도망 버튼을 사용하세요.")

    narrative = await ollama.generate_narrative(player, action.action)
    narrative_ok = not narrative.startswith("[")  # 폴백 오류 메시지는 대괄호로 시작

    # 매 턴 AI를 여러 번 부르면 느려지므로 부가 기능은 확률적으로만 실행.
    # 서사 생성이 이미 실패(시간 초과 등)했다면 추가 호출로 지연을 더 쌓지 않는다.
    special_event = None
    if narrative_ok and random.random() < SPECIAL_EVENT_CHANCE:
        special_event = await ollama.generate_special_event(player)

    # 단기 기억에 기록 (다음 턴부터 AI가 이 대화를 참조)
    player.add_history("플레이어", action.action)
    player.add_history("나레이터", narrative)
    if special_event:
        player.add_history("시스템", special_event)

    # 서사에서 상태 변화 추출 및 적용 (AI 제안, 코드가 범위 강제)
    event_logs = []
    if narrative_ok and USE_AI_GENERATION and random.random() < STORY_EVENT_CHANCE:
        event_logs = await _apply_story_events(player, narrative)

    # 대화가 쌓이면 오래된 부분을 백그라운드에서 요약에 병합
    _maybe_compress_memory(player, background_tasks)

    save_player_state(player)

    response_data = {
        "narrative": narrative,
        "player": player.dict(),
    }

    if event_logs:
        response_data["event_logs"] = event_logs
    if special_event:
        response_data["special_event"] = special_event

    return response_data


@app.post("/api/game/action/stream")
async def perform_action_stream(action: PlayerAction, background_tasks: BackgroundTasks):
    """나레이터 응답을 토큰 단위로 즉시 전송 (NDJSON).

    각 줄은 JSON 객체:
    - {"type": "chunk", "text": "..."}  이야기 조각 (도착하는 대로 여러 번)
    - {"type": "done", "narrative": "...", "player": {...}, "special_event": "..."}  완료 시 1회
    """
    player = load_player_state()

    if player.current_enemy:
        raise HTTPException(status_code=400, detail="전투 중에는 행동할 수 없습니다. 공격 또는 도망 버튼을 사용하세요.")

    async def event_generator():
        full_narrative = ""
        async for chunk in ollama.generate_narrative_stream(player, action.action):
            full_narrative += chunk
            yield json.dumps({"type": "chunk", "text": chunk}, ensure_ascii=False) + "\n"

        narrative_ok = not full_narrative.startswith("[")

        # 매 턴 AI를 여러 번 부르면 느려지므로 부가 기능은 확률적으로만 실행.
        # 서사 생성이 이미 실패(시간 초과 등)했다면 추가 호출로 지연을 더 쌓지 않는다.
        special_event = None
        if narrative_ok and random.random() < SPECIAL_EVENT_CHANCE:
            special_event = await ollama.generate_special_event(player)

        player.add_history("플레이어", action.action)
        player.add_history("나레이터", full_narrative)
        if special_event:
            player.add_history("시스템", special_event)

        # 서사에서 상태 변화 추출 및 적용 (AI 제안, 코드가 범위 강제)
        event_logs = []
        if narrative_ok and USE_AI_GENERATION and random.random() < STORY_EVENT_CHANCE:
            event_logs = await _apply_story_events(player, full_narrative)

        _maybe_compress_memory(player, background_tasks)
        save_player_state(player)

        done_payload = {
            "type": "done",
            "narrative": full_narrative,
            "player": player.dict(),
        }
        if event_logs:
            done_payload["event_logs"] = event_logs
        if special_event:
            done_payload["special_event"] = special_event

        yield json.dumps(done_payload, ensure_ascii=False) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/api/inventory/equip")
async def equip_item(item_id: str):
    player = load_player_state()

    item = next((i for i in player.inventory.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    if item.item_type == ItemType.WEAPON:
        # 새 장비를 먼저 인벤토리에서 빼서 슬롯을 확보한 뒤 기존 장비를 넣는다.
        # (순서가 반대면 인벤토리가 가득할 때 기존 장비가 소멸)
        old_weapon = player.equipment.weapon
        player.inventory.remove_item(item_id, 1)
        if old_weapon and not player.inventory.add_item(old_weapon):
            player.inventory.add_item(item)  # 원상복구
            raise HTTPException(status_code=400, detail="인벤토리가 가득 차서 장비를 교체할 수 없습니다")
        player.equipment.weapon = item
        save_player_state(player)
        return {
            "message": f"{item.name}을(를) 장착했습니다",
            "player": player.dict()
        }
    elif item.item_type == ItemType.ARMOR:
        old_armor = player.equipment.armor
        player.inventory.remove_item(item_id, 1)
        if old_armor and not player.inventory.add_item(old_armor):
            player.inventory.add_item(item)  # 원상복구
            raise HTTPException(status_code=400, detail="인벤토리가 가득 차서 장비를 교체할 수 없습니다")
        player.equipment.armor = item
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
        if not player.equipment.weapon:
            raise HTTPException(status_code=400, detail="장착된 무기가 없습니다")
        # 인벤토리에 못 넣으면 해제 자체를 거부 (아이템 소멸 방지)
        if not player.inventory.add_item(player.equipment.weapon):
            raise HTTPException(status_code=400, detail="인벤토리가 가득 차서 해제할 수 없습니다")
        player.equipment.weapon = None
    elif slot == "armor":
        if not player.equipment.armor:
            raise HTTPException(status_code=400, detail="장착된 방어구가 없습니다")
        if not player.inventory.add_item(player.equipment.armor):
            raise HTTPException(status_code=400, detail="인벤토리가 가득 차서 해제할 수 없습니다")
        player.equipment.armor = None
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


@app.post("/api/admin/compress-memory")
async def admin_compress_memory():
    """자정 강제 압축 트리거 (systemd 타이머가 매일 00:00에 호출).

    인증 없이 열려 있음 - 이 프로젝트는 개인용/로컬 운영 전제이며
    호출해도 상태를 훼손하지 않고(요약 병합만 수행) 부작용이 없다.
    """
    result = await force_compress_now()
    return {"message": "기억 압축 완료", **result}


@app.get("/api/ollama/models")
async def ollama_models():
    """설치된 Ollama 모델 목록 + 현재 사용 중인 모델"""
    models = await ollama.list_models()
    return {"models": models, "current": ollama.model}


@app.post("/api/ollama/model")
async def set_ollama_model(name: str):
    """사용할 모델 변경 (서버 재시작 시 초기화 - 영구 변경은 OLLAMA_MODEL 환경변수)"""
    models = await ollama.list_models()
    if models and name not in models:
        raise HTTPException(status_code=400, detail=f"설치되지 않은 모델입니다: {name}")

    ollama.model = name
    logger.info("모델 변경: %s", name)
    return {"message": f"모델을 {name}(으)로 변경했습니다", "current": name}


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
