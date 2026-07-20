from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class JobClass(str, Enum):
    WARRIOR = "warrior"
    ROGUE = "rogue"
    MAGE = "mage"
    PALADIN = "paladin"
    RANGER = "ranger"


class ItemType(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    QUEST_ITEM = "quest_item"
    SPECIAL = "special"


class Item(BaseModel):
    id: str
    name: str
    description: str
    item_type: ItemType
    effect: Dict[str, Any] = Field(default_factory=dict)
    quantity: int = 1
    price: int = 0  # 동적 생성 아이템도 판매 가능하도록 가격 보유


class Equipment(BaseModel):
    weapon: Optional[Item] = None
    armor: Optional[Item] = None


class Enemy(BaseModel):
    id: str
    name: str
    level: int = 1
    hp: int
    max_hp: int
    attack: int
    defense: int
    xp_reward: int = 0
    gold_reward: int = 0


class Quest(BaseModel):
    id: str
    title: str
    quest_type: str = "hunt"        # hunt(처치) / boss(보스 토벌) / explore(탐험)
    target_enemy_id: str = ""       # 구버전 호환용
    target_location: str = ""       # 동적 몬스터 대응: 지역 기반 처치 퀘스트
    target_count: int
    progress: int = 0
    reward_gold: int = 0
    reward_xp: int = 0
    visited_locations: List[str] = Field(default_factory=list)  # 탐험 퀘스트: 중복 방문 방지


class Inventory(BaseModel):
    items: List[Item] = Field(default_factory=list)
    max_slots: int = 20

    def add_item(self, item: Item) -> bool:
        existing = next((i for i in self.items if i.id == item.id), None)
        if existing:
            existing.quantity += item.quantity
            return True
        elif len(self.items) < self.max_slots:
            self.items.append(item)
            return True
        return False

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        item = next((i for i in self.items if i.id == item_id), None)
        if item:
            item.quantity -= quantity
            if item.quantity <= 0:
                self.items.remove(item)
            return True
        return False

    def has_item(self, item_id: str) -> bool:
        return any(i.id == item_id for i in self.items)


class PlayerState(BaseModel):
    name: str = "모험가"
    job_class: JobClass = JobClass.WARRIOR
    level: int = 1
    hp: int = 100
    max_hp: int = 100
    mp: int = 30
    max_mp: int = 30
    attack: int = 10
    defense: int = 5
    experience: int = 0
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    inventory: Inventory = Field(default_factory=Inventory)
    equipment: Equipment = Field(default_factory=Equipment)
    location: str = "교차로 마을"
    quest_log: List[str] = Field(default_factory=list)
    job_selected: bool = False
    story_summary: str = ""
    recent_history: List[Dict[str, str]] = Field(default_factory=list)
    pending_summary: List[Dict[str, str]] = Field(default_factory=list)  # 요약 대기 중 (재시작 유실 방지)
    gold: int = 50
    current_enemy: Optional[Enemy] = None
    active_quests: List[Quest] = Field(default_factory=list)
    completed_quests: List[Dict[str, Any]] = Field(default_factory=list)  # 완료 기록 (최근 N개)
    stats_kills: int = 0
    stats_deaths: int = 0
    stats_quests_completed: int = 0
    # 상태 이상: [{"type": "poison"|"stun", "turns": 남은 턴}]
    status_effects: List[Dict[str, Any]] = Field(default_factory=list)
    is_game_over: bool = False  # 사망 후 "다시하기" 대기 상태

    def add_history(self, role: str, content: str) -> None:
        """대화 기록 추가 (단기 기억)"""
        self.recent_history.append({"role": role, "content": content})

    def take_damage(self, damage: int) -> int:
        actual_damage = max(1, damage - self.get_effective_defense())
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_mp(self, amount: int) -> None:
        self.mp = min(self.max_mp, self.mp + amount)

    def apply_mp_migration(self) -> None:
        """마나 도입 이전 세이브에 직업/레벨 기준 마나를 소급 적용"""
        base_mp = {
            JobClass.WARRIOR: 30, JobClass.ROGUE: 40, JobClass.MAGE: 80,
            JobClass.PALADIN: 60, JobClass.RANGER: 50,
        }
        growth_mp = {
            JobClass.WARRIOR: 3, JobClass.ROGUE: 5, JobClass.MAGE: 10,
            JobClass.PALADIN: 8, JobClass.RANGER: 6,
        }
        self.max_mp = base_mp.get(self.job_class, 30) + growth_mp.get(self.job_class, 3) * (self.level - 1)
        self.mp = self.max_mp

    def has_status(self, effect_type: str) -> bool:
        return any(e.get("type") == effect_type for e in self.status_effects)

    def add_status(self, effect_type: str, turns: int) -> None:
        """상태 이상 부여 (이미 걸려 있으면 지속 턴만 갱신)"""
        existing = next((e for e in self.status_effects if e.get("type") == effect_type), None)
        if existing:
            existing["turns"] = max(existing["turns"], turns)
        else:
            self.status_effects.append({"type": effect_type, "turns": turns})

    def clear_status(self) -> None:
        self.status_effects = []

    def get_effective_defense(self) -> int:
        base_defense = self.defense
        if self.equipment.armor:
            base_defense += self.equipment.armor.effect.get("defense_bonus", 0)
        return base_defense

    def exp_required(self) -> int:
        return self.level * 100

    def gain_experience(self, amount: int) -> int:
        """경험치를 획득하고, 올라간 레벨 수를 반환"""
        self.experience += amount
        levels_gained = 0
        while self.experience >= self.exp_required():
            self.experience -= self.exp_required()
            self._level_up()
            levels_gained += 1
        return levels_gained

    def _level_up(self) -> None:
        self.level += 1

        growth = {
            JobClass.WARRIOR: {"hp": 15, "mp": 3, "attack": 3, "defense": 2, "strength": 2, "dexterity": 1, "intelligence": 1},
            JobClass.ROGUE: {"hp": 10, "mp": 5, "attack": 2, "defense": 1, "strength": 1, "dexterity": 3, "intelligence": 1},
            JobClass.MAGE: {"hp": 8, "mp": 10, "attack": 2, "defense": 1, "strength": 1, "dexterity": 1, "intelligence": 3},
            JobClass.PALADIN: {"hp": 13, "mp": 8, "attack": 2, "defense": 2, "strength": 2, "dexterity": 1, "intelligence": 2},
            JobClass.RANGER: {"hp": 11, "mp": 6, "attack": 2, "defense": 1, "strength": 2, "dexterity": 2, "intelligence": 1},
        }

        g = growth.get(self.job_class, growth[JobClass.WARRIOR])
        self.max_hp += g["hp"]
        self.hp = self.max_hp
        self.max_mp += g["mp"]
        self.mp = self.max_mp
        self.attack += g["attack"]
        self.defense += g["defense"]
        self.strength += g["strength"]
        self.dexterity += g["dexterity"]
        self.intelligence += g["intelligence"]

    def get_effective_attack(self) -> int:
        ability_bonus = 0

        if self.job_class == JobClass.WARRIOR:
            ability_bonus = self.strength // 2
        elif self.job_class == JobClass.ROGUE:
            ability_bonus = self.dexterity // 2
        elif self.job_class == JobClass.MAGE:
            ability_bonus = self.intelligence // 2
        elif self.job_class == JobClass.PALADIN:
            ability_bonus = (self.strength + self.dexterity + self.intelligence) // 9
        elif self.job_class == JobClass.RANGER:
            ability_bonus = (self.strength + self.dexterity) // 4

        base_attack = self.attack + ability_bonus
        if self.equipment.weapon:
            base_attack += self.equipment.weapon.effect.get("attack_bonus", 0)
        return base_attack

    def set_job_class(self, job: JobClass) -> None:
        self.job_class = job
        self.job_selected = True

        job_stats = {
            JobClass.WARRIOR: {
                "strength": 15,
                "dexterity": 8,
                "intelligence": 7,
                "hp": 120,
                "mp": 30,
                "attack": 12,
                "defense": 8
            },
            JobClass.ROGUE: {
                "strength": 10,
                "dexterity": 15,
                "intelligence": 8,
                "hp": 90,
                "mp": 40,
                "attack": 11,
                "defense": 4
            },
            JobClass.MAGE: {
                "strength": 7,
                "dexterity": 10,
                "intelligence": 16,
                "hp": 80,
                "mp": 80,
                "attack": 8,
                "defense": 3
            },
            JobClass.PALADIN: {
                "strength": 13,
                "dexterity": 9,
                "intelligence": 11,
                "hp": 110,
                "mp": 60,
                "attack": 11,
                "defense": 9
            },
            JobClass.RANGER: {
                "strength": 11,
                "dexterity": 14,
                "intelligence": 9,
                "hp": 95,
                "mp": 50,
                "attack": 10,
                "defense": 5
            }
        }

        stats = job_stats.get(job, job_stats[JobClass.WARRIOR])
        self.strength = stats["strength"]
        self.dexterity = stats["dexterity"]
        self.intelligence = stats["intelligence"]
        self.hp = stats["hp"]
        self.max_hp = stats["hp"]
        self.mp = stats["mp"]
        self.max_mp = stats["mp"]
        self.attack = stats["attack"]
        self.defense = stats["defense"]

    def dict(self, **kwargs) -> Dict[str, Any]:
        from skills_db import get_available_skills
        data = super().model_dump(**kwargs)
        # 프론트엔드 표시용 계산 스탯 (저장 시 무시됨)
        data["effective_attack"] = self.get_effective_attack()
        data["effective_defense"] = self.get_effective_defense()
        data["exp_required"] = self.exp_required()
        data["skills"] = get_available_skills(self.job_class.value, self.level)
        return data


class PlayerAction(BaseModel):
    action: str
    target: Optional[str] = None


class AIResponse(BaseModel):
    narrative: str
    state_changes: Dict[str, Any] = Field(default_factory=dict)
    special_event: Optional[str] = None


class GameMessage(BaseModel):
    role: str
    content: str
    type: str = "narrative"
