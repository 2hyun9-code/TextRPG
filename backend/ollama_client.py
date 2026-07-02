import httpx
import json
import re
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

        quest_info = "; ".join(
            f"{q.title} ({q.progress}/{q.target_count})"
            for q in player_state.active_quests
        ) or "없음"

        return f"""당신은 텍스트 RPG 모험의 나레이터입니다. 플레이어는 {player_state.name}, 레벨 {player_state.level} {job_name}입니다.
{story_context}
현재 상태:
- 체력: {player_state.hp}/{player_state.max_hp}
- 공격: {player_state.get_effective_attack()}
- 방어: {player_state.get_effective_defense()}
- 골드: {player_state.gold}
- 위치: {player_state.location}
- 진행 중인 퀘스트: {quest_info}
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
6. 가능한 다음 행동을 제안하되 강요하지 마세요
7. 이야기 요약에 담긴 목표와 사건을 자연스럽게 이어가세요. 단, 플레이어가 다른 길을 선택하면 그 선택을 존중하고 이야기를 그 방향으로 전개하세요"""

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

    async def _generate_json(self, prompt: str, timeout: float = 30.0) -> Optional[dict]:
        """JSON 강제 모드로 생성. 실패 시 None (폴백은 호출자 책임)"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=timeout
            )
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            # JSON 블록 추출 (모델이 여분 텍스트를 붙이는 경우 대비)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            return None
        except Exception:
            return None

    async def generate_enemy_concept(self, player_state: PlayerState) -> Optional[dict]:
        """현재 이야기 맥락에 어울리는 독창적 몬스터를 AI가 창작"""
        story = player_state.story_summary or "모험이 막 시작되었다."

        prompt = f"""당신은 텍스트 RPG의 몬스터 디자이너입니다.

장소: {player_state.location}
이야기 맥락: {story}

이 장소와 이야기에 어울리는 독창적인 몬스터 하나를 한국어로 창작하세요.
유명 게임의 몬스터를 그대로 복사하지 말고 새로운 존재를 만드세요.

반드시 이 JSON 형식으로만 답하세요:
{{"name": "몬스터 이름 (2~10글자)", "description": "생김새와 분위기를 담은 한 문장"}}"""

        data = await self._generate_json(prompt)
        if not data:
            return None

        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()

        # 검증: 이름이 비었거나 비정상적으로 길면 폴백
        if not name or len(name) > 20:
            return None

        return {"name": name, "description": description[:100]}

    async def generate_item_concept(self, player_state: PlayerState, kind: str) -> Optional[dict]:
        """전리품 장비의 이름/묘사를 AI가 창작 (스탯은 코드가 결정)"""
        kind_kr = "무기" if kind == "weapon" else "방어구"
        enemy_name = player_state.current_enemy.name if player_state.current_enemy else "쓰러진 적"

        prompt = f"""당신은 텍스트 RPG의 아이템 디자이너입니다.

장소: {player_state.location}
방금 쓰러뜨린 적: {enemy_name}

이 적이 남길 법한 독창적인 {kind_kr} 하나를 한국어로 창작하세요.

반드시 이 JSON 형식으로만 답하세요:
{{"name": "{kind_kr} 이름 (2~12글자)", "description": "한 문장 묘사"}}"""

        data = await self._generate_json(prompt)
        if not data:
            return None

        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()

        if not name or len(name) > 24:
            return None

        return {"name": name, "description": description[:100]}

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
