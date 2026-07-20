"""직업별 전투 스킬 정의

스킬은 전투 중 마나(MP)를 소모해 사용한다.
- damage_mult: 유효 공격력 배율
- int_scale: 지능 계수 (마법 계열은 지능이 피해에 추가됨)
- ignore_defense: 적 방어 무시 여부
- self_heal_int: 사용 시 지능 x 계수만큼 자기 회복
"""

SKILLS = {
    "warrior": {
        "id": "power_strike",
        "name": "강타",
        "description": "온 힘을 실어 내려친다. 피해 2배.",
        "mp_cost": 10,
        "damage_mult": 2.0,
        "int_scale": 0,
        "ignore_defense": False,
        "self_heal_int": 0,
    },
    "rogue": {
        "id": "ambush",
        "name": "급습",
        "description": "빈틈을 파고든다. 피해 1.8배.",
        "mp_cost": 8,
        "damage_mult": 1.8,
        "int_scale": 0,
        "ignore_defense": False,
        "self_heal_int": 0,
    },
    "mage": {
        "id": "fireball",
        "name": "화염구",
        "description": "화염 덩어리를 던진다. 피해에 지능 x2 추가.",
        "mp_cost": 12,
        "damage_mult": 1.0,
        "int_scale": 2,
        "ignore_defense": False,
        "self_heal_int": 0,
    },
    "paladin": {
        "id": "holy_light",
        "name": "심판의 빛",
        "description": "빛으로 내려친다. 피해 1.5배 + 지능 x2만큼 자기 회복.",
        "mp_cost": 12,
        "damage_mult": 1.5,
        "int_scale": 0,
        "ignore_defense": False,
        "self_heal_int": 2,
    },
    "ranger": {
        "id": "piercing_shot",
        "name": "관통 사격",
        "description": "약점을 꿰뚫는다. 피해 1.7배, 적 방어 무시.",
        "mp_cost": 10,
        "damage_mult": 1.7,
        "int_scale": 0,
        "ignore_defense": True,
        "self_heal_int": 0,
    },
}


def get_skill(job: str) -> dict:
    return SKILLS.get(job, SKILLS["warrior"])
