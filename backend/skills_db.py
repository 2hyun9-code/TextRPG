"""직업별 전투 스킬 정의 (레벨에 따라 성장)

각 직업은 레벨 1부터 쓰는 주력 스킬이 레벨 5에 강화되고,
레벨 10부터는 두 번째 스킬이 추가로 열린다 (주력 스킬은 계속 유지).

스킬 필드:
- damage_mult: 유효 공격력 배율
- int_scale: 지능 계수 (마법 계열은 지능이 피해에 추가됨)
- ignore_defense: 적 방어 무시 여부
- self_heal_int: 사용 시 지능 x 계수만큼 자기 회복
"""

SKILL_TIERS = {
    "warrior": {
        "primary": [
            {"min_level": 1, "id": "power_strike", "name": "강타",
             "description": "온 힘을 실어 내려친다. 피해 2배.",
             "mp_cost": 10, "damage_mult": 2.0, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 0},
            {"min_level": 5, "id": "power_strike_2", "name": "강타+",
             "description": "더욱 강해진 일격. 피해 2.6배.",
             "mp_cost": 10, "damage_mult": 2.6, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 0},
        ],
        "secondary": {
            "min_level": 10, "id": "execute", "name": "필살의 일격",
            "description": "적의 급소를 노려 방어를 무시하고 꿰뚫는다.",
            "mp_cost": 18, "damage_mult": 3.2, "int_scale": 0,
            "ignore_defense": True, "self_heal_int": 0,
        },
    },
    "rogue": {
        "primary": [
            {"min_level": 1, "id": "ambush", "name": "급습",
             "description": "빈틈을 파고든다. 피해 1.8배.",
             "mp_cost": 8, "damage_mult": 1.8, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 0},
            {"min_level": 5, "id": "ambush_2", "name": "급습+",
             "description": "더 날카로워진 기습. 피해 2.2배.",
             "mp_cost": 8, "damage_mult": 2.2, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 0},
        ],
        "secondary": {
            "min_level": 10, "id": "shadow_strike", "name": "그림자 습격",
            "description": "그림자 속에서 나타나 급소를 찌른다.",
            "mp_cost": 16, "damage_mult": 2.8, "int_scale": 0,
            "ignore_defense": False, "self_heal_int": 0,
        },
    },
    "mage": {
        "primary": [
            {"min_level": 1, "id": "fireball", "name": "화염구",
             "description": "화염 덩어리를 던진다. 피해에 지능 x2 추가.",
             "mp_cost": 12, "damage_mult": 1.0, "int_scale": 2,
             "ignore_defense": False, "self_heal_int": 0},
            {"min_level": 5, "id": "fireball_2", "name": "화염구+",
             "description": "더 뜨거워진 화염구. 피해에 지능 x2.6 추가.",
             "mp_cost": 12, "damage_mult": 1.0, "int_scale": 2.6,
             "ignore_defense": False, "self_heal_int": 0},
        ],
        "secondary": {
            "min_level": 10, "id": "chain_lightning", "name": "연쇄 번개",
            "description": "번개가 적을 연달아 강타한다.",
            "mp_cost": 20, "damage_mult": 1.2, "int_scale": 2.5,
            "ignore_defense": False, "self_heal_int": 0,
        },
    },
    "paladin": {
        "primary": [
            {"min_level": 1, "id": "holy_light", "name": "심판의 빛",
             "description": "빛으로 내려친다. 피해 1.5배 + 지능 x2 자기 회복.",
             "mp_cost": 12, "damage_mult": 1.5, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 2},
            {"min_level": 5, "id": "holy_light_2", "name": "심판의 빛+",
             "description": "더 강해진 심판. 피해 1.8배 + 지능 x2.4 자기 회복.",
             "mp_cost": 12, "damage_mult": 1.8, "int_scale": 0,
             "ignore_defense": False, "self_heal_int": 2.4},
        ],
        "secondary": {
            "min_level": 10, "id": "divine_judgment", "name": "성스러운 심판",
            "description": "신성한 힘으로 방어를 무시하고 내려친다.",
            "mp_cost": 22, "damage_mult": 2.2, "int_scale": 0,
            "ignore_defense": True, "self_heal_int": 1.5,
        },
    },
    "ranger": {
        "primary": [
            {"min_level": 1, "id": "piercing_shot", "name": "관통 사격",
             "description": "약점을 꿰뚫는다. 피해 1.7배, 적 방어 무시.",
             "mp_cost": 10, "damage_mult": 1.7, "int_scale": 0,
             "ignore_defense": True, "self_heal_int": 0},
            {"min_level": 5, "id": "piercing_shot_2", "name": "관통 사격+",
             "description": "더 정교해진 사격. 피해 2.0배, 적 방어 무시.",
             "mp_cost": 10, "damage_mult": 2.0, "int_scale": 0,
             "ignore_defense": True, "self_heal_int": 0},
        ],
        "secondary": {
            "min_level": 10, "id": "storm_shot", "name": "폭풍 사격",
            "description": "화살비를 퍼부어 적을 꿰뚫는다.",
            "mp_cost": 18, "damage_mult": 2.5, "int_scale": 0,
            "ignore_defense": True, "self_heal_int": 0,
        },
    },
}


def get_available_skills(job: str, level: int) -> list:
    """플레이어 레벨에서 사용 가능한 스킬 목록.

    주력 스킬은 항상 1개(레벨에 따라 강화된 버전), 레벨 10부터
    보조 스킬이 추가되어 최대 2개가 된다.
    """
    tiers = SKILL_TIERS.get(job, SKILL_TIERS["warrior"])

    primary = tiers["primary"][0]
    for tier in tiers["primary"]:
        if level >= tier["min_level"]:
            primary = tier

    skills = [primary]

    secondary = tiers.get("secondary")
    if secondary and level >= secondary["min_level"]:
        skills.append(secondary)

    return skills


def get_skill_by_id(job: str, level: int, skill_id: str) -> dict:
    """스킬 사용 요청 검증: 현재 레벨에서 실제로 쓸 수 있는 스킬이면 반환, 아니면 None"""
    for skill in get_available_skills(job, level):
        if skill["id"] == skill_id:
            return skill
    return None


def get_skill(job: str) -> dict:
    """구버전 호환: 레벨 무관 기본(1단계) 스킬 반환"""
    tiers = SKILL_TIERS.get(job, SKILL_TIERS["warrior"])
    return tiers["primary"][0]
