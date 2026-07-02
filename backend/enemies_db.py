"""적 데이터베이스 - 몬스터 정의와 레벨 기반 조우 로직"""

import random
from models import Enemy

ENEMY_TEMPLATES = [
    {"id": "slime", "name": "슬라임", "level": 1, "hp": 30, "attack": 6, "defense": 1, "xp": 25, "gold": 10},
    {"id": "goblin", "name": "고블린", "level": 2, "hp": 45, "attack": 9, "defense": 2, "xp": 40, "gold": 18},
    {"id": "wolf", "name": "들늑대", "level": 3, "hp": 60, "attack": 13, "defense": 3, "xp": 60, "gold": 25},
    {"id": "skeleton", "name": "해골 병사", "level": 4, "hp": 75, "attack": 16, "defense": 5, "xp": 85, "gold": 40},
    {"id": "orc", "name": "오크 전사", "level": 5, "hp": 100, "attack": 20, "defense": 7, "xp": 120, "gold": 60},
    {"id": "bandit", "name": "산적 두목", "level": 6, "hp": 120, "attack": 24, "defense": 8, "xp": 160, "gold": 100},
    {"id": "troll", "name": "동굴 트롤", "level": 7, "hp": 160, "attack": 28, "defense": 10, "xp": 220, "gold": 140},
    {"id": "dark_knight", "name": "암흑 기사", "level": 9, "hp": 220, "attack": 35, "defense": 14, "xp": 350, "gold": 250},
    {"id": "wyvern", "name": "와이번", "level": 11, "hp": 300, "attack": 42, "defense": 16, "xp": 500, "gold": 400},
    {"id": "dragon", "name": "고대 드래곤", "level": 14, "hp": 450, "attack": 55, "defense": 22, "xp": 900, "gold": 800},
]

# 적 처치 시 드롭 테이블: (아이템 id, 드롭 확률)
DROP_TABLES = {
    "slime": [("small_potion", 0.30)],
    "goblin": [("small_potion", 0.25), ("rusty_sword", 0.10)],
    "wolf": [("small_potion", 0.30), ("leather_armor", 0.10)],
    "skeleton": [("medium_potion", 0.20), ("iron_sword", 0.08)],
    "orc": [("medium_potion", 0.25), ("iron_sword", 0.12), ("chain_mail", 0.06)],
    "bandit": [("medium_potion", 0.30), ("hunting_bow", 0.12)],
    "troll": [("large_potion", 0.20), ("chain_mail", 0.12)],
    "dark_knight": [("large_potion", 0.30), ("steel_sword", 0.12), ("plate_armor", 0.08)],
    "wyvern": [("large_potion", 0.40), ("plate_armor", 0.12)],
    "dragon": [("large_potion", 0.60), ("steel_sword", 0.25), ("plate_armor", 0.20)],
}


def get_random_enemy(player_level: int) -> Enemy:
    """플레이어 레벨에 맞는 적을 무작위로 선택"""
    candidates = [t for t in ENEMY_TEMPLATES if abs(t["level"] - player_level) <= 2]
    if not candidates:
        # 범위 내 적이 없으면 가장 가까운 레벨의 적 선택
        candidates = sorted(ENEMY_TEMPLATES, key=lambda t: abs(t["level"] - player_level))[:3]

    template = random.choice(candidates)

    # 약간의 개체 편차 (90% ~ 110%)
    variance = random.uniform(0.9, 1.1)
    hp = int(template["hp"] * variance)

    return Enemy(
        id=template["id"],
        name=template["name"],
        level=template["level"],
        hp=hp,
        max_hp=hp,
        attack=int(template["attack"] * variance),
        defense=template["defense"],
        xp_reward=template["xp"],
        gold_reward=int(template["gold"] * random.uniform(0.8, 1.3)),
    )


def roll_drop(enemy_id: str):
    """적 처치 시 드롭 아이템 결정. 없으면 None"""
    table = DROP_TABLES.get(enemy_id, [])
    for item_id, chance in table:
        if random.random() < chance:
            return item_id
    return None
