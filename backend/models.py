from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


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
    level: int = 1
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    defense: int = 5
    experience: int = 0
    inventory: Inventory = Field(default_factory=Inventory)
    equipment: Equipment = Field(default_factory=Equipment)
    location: str = "교차로 마을"
    quest_log: List[str] = Field(default_factory=list)

    def take_damage(self, damage: int) -> int:
        actual_damage = max(1, damage - self.defense)
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def get_effective_attack(self) -> int:
        base_attack = self.attack
        if self.equipment.weapon:
            base_attack += self.equipment.weapon.effect.get("attack_bonus", 0)
        return base_attack

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
