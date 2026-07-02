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


class Equipment(BaseModel):
    weapon: Optional[Item] = None
    armor: Optional[Item] = None


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

    def take_damage(self, damage: int) -> int:
        actual_damage = max(1, damage - self.defense)
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def get_effective_attack(self) -> int:
        base_attack = self.attack + (self.strength // 2)
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
                "attack": 12,
                "defense": 8
            },
            JobClass.ROGUE: {
                "strength": 10,
                "dexterity": 15,
                "intelligence": 8,
                "hp": 90,
                "attack": 11,
                "defense": 4
            },
            JobClass.MAGE: {
                "strength": 7,
                "dexterity": 10,
                "intelligence": 16,
                "hp": 80,
                "attack": 8,
                "defense": 3
            },
            JobClass.PALADIN: {
                "strength": 13,
                "dexterity": 9,
                "intelligence": 11,
                "hp": 110,
                "attack": 11,
                "defense": 9
            },
            JobClass.RANGER: {
                "strength": 11,
                "dexterity": 14,
                "intelligence": 9,
                "hp": 95,
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
        self.attack = stats["attack"]
        self.defense = stats["defense"]

    def dict(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)


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
