import httpx
import json
from typing import Optional
from models import PlayerState, AIResponse


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "gemma2:2b"
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self.client.aclose()

    def _build_system_prompt(self, player_state: PlayerState) -> str:
        weapon_info = f"장착된 무기: {player_state.equipment.weapon.name} (+{player_state.equipment.weapon.effect.get('attack_bonus', 0)} 공격)" if player_state.equipment.weapon else "장착된 무기 없음"
        armor_info = f"장착된 방어구: {player_state.equipment.armor.name} (+{player_state.equipment.armor.effect.get('defense_bonus', 0)} 방어)" if player_state.equipment.armor else "장착된 방어구 없음"

        special_items = [item.name for item in player_state.inventory.items if item.item_type.value == "special"]
        special_info = f"특수 아이템: {', '.join(special_items)}" if special_items else "특수 아이템 없음"

        story_context = ""
        if player_state.story_summary:
            story_context = f"\n이전 이야기 요약:\n{player_state.story_summary}\n"

        return f"""당신은 텍스트 RPG 모험의 나레이터입니다. 플레이어는 {player_state.name}, 레벨 {player_state.level}입니다.
{story_context}
현재 상태:
- 체력: {player_state.hp}/{player_state.max_hp}
- 공격: {player_state.get_effective_attack()}
- 방어: {player_state.defense}
- 위치: {player_state.location}
- {weapon_info}
- {armor_info}
- {special_info}

인벤토리 ({len(player_state.inventory.items)}/{player_state.inventory.max_slots}):
{self._format_inventory(player_state)}

지시사항:
1. 플레이어의 행동 결과를 창의적으로 묘사하는 나레이터로 응답하세요
2. 응답은 간결하게 유지하세요 (2-3 문장)
3. 장착된 아이템에 반응하세요 - 관련될 때 서사에서 그 효과를 언급하세요
4. 플레이어가 지도를 가지고 있으면 가끔 새로운 지역 탐험을 제안하세요
5. 매력적이고 몰입감 있게 하세요
6. 가능한 다음 행동을 제안하되 강요하지 마세요"""

    def _format_inventory(self, player_state: PlayerState) -> str:
        if not player_state.inventory.items:
            return "- Empty"
        return "\n".join([f"- {item.name} x{item.quantity}" for item in player_state.inventory.items])

    async def generate_narrative(self, player_state: PlayerState, player_action: str) -> str:
        system_prompt = self._build_system_prompt(player_state)

        prompt = f"{system_prompt}\n\nPlayer action: {player_action}"

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "공기가 고요해진다...").strip()
        except Exception as e:
            return f"[나레이터의 목소리가 희미해진다... 연결 오류: {str(e)}]"

    async def summarize_messages(self, messages: list) -> str:
        if not messages:
            return ""

        message_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages[-50:]
        ])

        prompt = f"""다음은 게임 진행 중 지난 이야기의 일부입니다. 이 내용을 2-3 문장으로 요약해주세요.
지금까지의 주요 사건과 플레이어의 상황을 포함해서요.

이야기:
{message_text}

요약:"""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except Exception:
            return "이전 이야기 요약을 불러올 수 없습니다."

    async def generate_special_event(self, player_state: PlayerState) -> Optional[str]:
        if not player_state.inventory.has_item("map"):
            return None

        prompt = f"""당신은 텍스트 RPG의 퀘스트 생성기입니다. 이 모험가의 상태를 바탕으로 하나의 간단한 무작위 퀘스트 훅을 생성하세요 (1-2 문장).

플레이어: {player_state.name}, 레벨 {player_state.level}
현재 위치: {player_state.location}

플레이어의 현재 레벨과 위치에 맞는 퀘스트 훅을 생성하세요. 흥미롭지만 간결하게 하세요."""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                }
            )
            response.raise_for_status()
            result = response.json()
            quest = result.get("response", "").strip()
            return f"[새로운 퀘스트] {quest}" if quest else None
        except Exception:
            return None
