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

        job_names = {
            "warrior": "전사", "rogue": "도적", "mage": "마법사",
            "paladin": "성기사", "ranger": "레인저"
        }
        job_name = job_names.get(player_state.job_class.value, "모험가")

        return f"""당신은 텍스트 RPG 모험의 나레이터입니다. 플레이어는 {player_state.name}, 레벨 {player_state.level} {job_name}입니다.
{story_context}
현재 상태:
- 체력: {player_state.hp}/{player_state.max_hp}
- 공격: {player_state.get_effective_attack()}
- 방어: {player_state.get_effective_defense()}
- 골드: {player_state.gold}
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

    def _format_recent_history(self, player_state: PlayerState, limit: int = 10) -> str:
        """최근 대화를 프롬프트용 텍스트로 변환 (단기 기억)"""
        if not player_state.recent_history:
            return ""

        lines = [
            f"{msg.get('role', '?')}: {msg.get('content', '')}"
            for msg in player_state.recent_history[-limit:]
        ]
        return "\n최근 대화:\n" + "\n".join(lines) + "\n"

    async def generate_narrative(self, player_state: PlayerState, player_action: str) -> str:
        system_prompt = self._build_system_prompt(player_state)
        history_text = self._format_recent_history(player_state)

        prompt = f"""{system_prompt}
{history_text}
플레이어 행동: {player_action}

나레이터 응답:"""

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

    async def update_summary(self, old_summary: str, messages: list) -> str:
        """증분 요약: 기존 요약과 새로운 사건을 병합해 갱신 (중기 기억)

        덮어쓰기가 아니라 병합이므로 오래된 기억도 압축된 형태로 계속 보존된다.
        """
        if not messages:
            return old_summary

        message_text = "\n".join([
            f"{msg.get('role', '?')}: {msg.get('content', '')}"
            for msg in messages
        ])

        existing = old_summary if old_summary else "(아직 없음 - 모험의 시작)"

        prompt = f"""당신은 텍스트 RPG의 기록가입니다. 기존 요약과 새로운 사건을 하나의 요약으로 병합하세요.

기존 요약:
{existing}

새로 일어난 사건:
{message_text}

병합 규칙:
1. 기존 요약의 중요한 내용은 유지하세요 (버리지 마세요)
2. 새로운 사건 중 중요한 것을 추가하세요
3. 만난 인물, 방문한 장소, 획득한 물건, 진행 중인 목표를 우선 보존하세요
4. 5문장 이내로 압축하세요
5. 요약문만 출력하세요 (다른 말 없이)

갱신된 요약:"""

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
            new_summary = result.get("response", "").strip()
            # 요약 생성 실패 시 기존 요약 유지 (기억 손실 방지)
            return new_summary if new_summary else old_summary
        except Exception:
            return old_summary

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
