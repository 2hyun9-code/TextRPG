"""아이템 데이터베이스 - 모든 아이템 정의를 한 곳에서 관리"""

from models import Item, ItemType

ITEMS_DB = {
    # 무기
    "rusty_sword": {
        "name": "녹슨 검",
        "description": "오래되어 녹슨 검. 없는 것보다는 낫다.",
        "item_type": ItemType.WEAPON,
        "effect": {"attack_bonus": 3},
        "price": 30
    },
    "iron_sword": {
        "name": "철검",
        "description": "튼튼한 철로 만든 검.",
        "item_type": ItemType.WEAPON,
        "effect": {"attack_bonus": 8},
        "price": 120
    },
    "steel_sword": {
        "name": "강철검",
        "description": "잘 벼려진 강철검. 날카로운 빛이 감돈다.",
        "item_type": ItemType.WEAPON,
        "effect": {"attack_bonus": 15},
        "price": 400
    },
    "hunting_bow": {
        "name": "사냥용 활",
        "description": "가볍고 다루기 쉬운 활.",
        "item_type": ItemType.WEAPON,
        "effect": {"attack_bonus": 7},
        "price": 100
    },
    "oak_staff": {
        "name": "참나무 지팡이",
        "description": "마력이 깃든 참나무 지팡이.",
        "item_type": ItemType.WEAPON,
        "effect": {"attack_bonus": 6},
        "price": 90
    },

    # 방어구
    "leather_armor": {
        "name": "가죽 갑옷",
        "description": "부드러운 가죽으로 만든 갑옷.",
        "item_type": ItemType.ARMOR,
        "effect": {"defense_bonus": 3},
        "price": 80
    },
    "chain_mail": {
        "name": "사슬 갑옷",
        "description": "촘촘한 사슬로 엮은 갑옷.",
        "item_type": ItemType.ARMOR,
        "effect": {"defense_bonus": 7},
        "price": 250
    },
    "plate_armor": {
        "name": "판금 갑옷",
        "description": "두꺼운 강철판으로 만든 갑옷.",
        "item_type": ItemType.ARMOR,
        "effect": {"defense_bonus": 12},
        "price": 600
    },

    # 소모품
    "small_potion": {
        "name": "소형 회복 물약",
        "description": "체력을 30 회복한다.",
        "item_type": ItemType.CONSUMABLE,
        "effect": {"heal": 30},
        "price": 20
    },
    "medium_potion": {
        "name": "중형 회복 물약",
        "description": "체력을 70 회복한다.",
        "item_type": ItemType.CONSUMABLE,
        "effect": {"heal": 70},
        "price": 50
    },
    "large_potion": {
        "name": "대형 회복 물약",
        "description": "체력을 150 회복한다.",
        "item_type": ItemType.CONSUMABLE,
        "effect": {"heal": 150},
        "price": 120
    },
    "torch": {
        "name": "나무 횃불",
        "description": "단순한 나무로 만든 횃불.",
        "item_type": ItemType.CONSUMABLE,
        "effect": {"light": 1},
        "price": 5
    },

    # 특수
    "map": {
        "name": "낡은 지도",
        "description": "근처 땅을 보여주는 오래된 지도.",
        "item_type": ItemType.SPECIAL,
        "effect": {"reveals_quests": True},
        "price": 0
    },
}

# 상점에서 판매하는 아이템 목록
SHOP_STOCK = [
    "rusty_sword", "iron_sword", "steel_sword", "hunting_bow", "oak_staff",
    "leather_armor", "chain_mail", "plate_armor",
    "small_potion", "medium_potion", "large_potion", "torch",
]


def create_item(item_id: str, quantity: int = 1) -> Item:
    """데이터베이스에서 아이템 인스턴스를 생성"""
    data = ITEMS_DB.get(item_id)
    if not data:
        raise KeyError(f"존재하지 않는 아이템: {item_id}")
    return Item(
        id=item_id,
        name=data["name"],
        description=data["description"],
        item_type=data["item_type"],
        effect=data["effect"],
        quantity=quantity,
        price=data["price"]
    )


def get_item_price(item_id: str) -> int:
    data = ITEMS_DB.get(item_id)
    return data["price"] if data else 0
