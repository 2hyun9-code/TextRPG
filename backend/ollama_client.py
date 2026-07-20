import httpx
import json
import logging
import os
import re
from typing import AsyncGenerator, Optional
from models import PlayerState, AIResponse

logger = logging.getLogger("textrpg.ollama")


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        # 환경변수로 코드 수정 없이 변경 가능:
        #   OLLAMA_URL=http://다른서버:11434 OLLAMA_MODEL=llama2-uncensored python run.py
        self.base_url = os.getenv("OLLAMA_URL", base_url)
        self.model = os.getenv("OLLAMA_MODEL", "gemma2:2b")
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self.client.aclose()

    async def list_models(self) -> list:
        """설치된 Ollama 모델 목록 (실패 시 빈 목록)"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]
        except Exception as e:
            logger.warning("모델 목록 조회 실패: %s", e)
            return []

    async def warmup(self) -> None:
        """서버 시작 시 모델을 미리 메모리에 로드해 첫 요청 지연을 없앤다."""
        try:
            await self.client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": "안녕", "stream": False},
                timeout=60.0
            )
            logger.info("Ollama 모델 프리워밍 완료: %s", self.model)
        except httpx.ConnectError:
            logger.warning("Ollama 서버에 연결할 수 없습니다. 프리워밍을 건너뜁니다.")
        except Exception as e:
            logger.warning("프리워밍 실패 (게임은 계속 진행됩니다): %s", e)

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
7. 이야기 요약에 담긴 목표와 사건을 자연스럽게 이어가세요. 단, 플레이어가 다른 길을 선택하면 그 선택을 존중하고 이야기를 그 방향으로 전개하세요

언어 규칙: 반드시 100% 한국어로만 응답하세요. 영어 단어나 알파벳을 단 한 글자도 섞지 마세요."""

    def _format_inventory(self, player_state: PlayerState) -> str:
        if not player_state.inventory.items:
            return "- 비어있음"
        return "\n".join([f"- {item.name} x{item.quantity}" for item in player_state.inventory.items])

    def _format_recent_history(self, player_state: PlayerState, limit: int = 20) -> str:
        """최근 대화를 프롬프트용 텍스트로 변환 (단기 기억)"""
        if not player_state.recent_history:
            return ""

        lines = [
            f"{msg.get('role', '?')}: {msg.get('content', '')}"
            for msg in player_state.recent_history[-limit:]
        ]
        return "\n최근 대화:\n" + "\n".join(lines) + "\n"

    def _build_action_prompt(self, player_state: PlayerState, player_action: str) -> str:
        system_prompt = self._build_system_prompt(player_state)
        history_text = self._format_recent_history(player_state)
        return f"""{system_prompt}
{history_text}
플레이어 행동: {player_action}

나레이터 응답:"""

    async def generate_narrative(self, player_state: PlayerState, player_action: str) -> str:
        prompt = self._build_action_prompt(player_state, player_action)

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    # 출력 길이를 못박아 응답 시간의 상한을 보장 (지시문의 "2-3문장"과 일치)
                    "options": {"num_predict": 100},
                },
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "공기가 고요해진다...").strip()
        except httpx.TimeoutException:
            logger.warning("나레이터 응답 시간 초과")
            return "[나레이터가 생각에 잠겨 말이 없다... 잠시 후 다시 시도해주세요]"
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패")
            return "[나레이터가 자리를 비웠다... Ollama가 실행 중인지 확인해주세요]"
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP 오류: %s", e)
            return "[나레이터가 말을 잇지 못한다... 잠시 후 다시 시도해주세요]"
        except Exception as e:
            logger.error("나레이터 생성 중 알 수 없는 오류: %s", e)
            return "[나레이터의 목소리가 희미해진다... 다시 시도해주세요]"

    async def generate_narrative_stream(
        self, player_state: PlayerState, player_action: str
    ) -> AsyncGenerator[str, None]:
        """토큰이 생성되는 대로 즉시 흘려보낸다 (체감 응답 속도 개선)"""
        prompt = self._build_action_prompt(player_state, player_action)

        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"num_predict": 100},
                },
                timeout=60.0
            ) as response:
                response.raise_for_status()
                got_any = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = data.get("response", "")
                    if chunk:
                        got_any = True
                        yield chunk
                if not got_any:
                    yield "공기가 고요해진다..."
        except httpx.TimeoutException:
            logger.warning("나레이터 스트리밍 응답 시간 초과")
            yield "[나레이터가 생각에 잠겨 말이 없다... 잠시 후 다시 시도해주세요]"
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패 (스트리밍)")
            yield "[나레이터가 자리를 비웠다... Ollama가 실행 중인지 확인해주세요]"
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP 오류 (스트리밍): %s", e)
            yield "[나레이터가 말을 잇지 못한다... 잠시 후 다시 시도해주세요]"
        except Exception as e:
            logger.error("나레이터 스트리밍 중 알 수 없는 오류: %s", e)
            yield "[나레이터의 목소리가 희미해진다... 다시 시도해주세요]"

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
6. 반드시 100% 한국어로만 작성하세요. 영어 단어나 알파벳을 단 한 글자도 섞지 마세요.

갱신된 요약:"""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 200},
                }
            )
            response.raise_for_status()
            result = response.json()
            new_summary = result.get("response", "").strip()
            # 요약 생성 실패 시 기존 요약 유지 (기억 손실 방지)
            return new_summary if new_summary else old_summary
        except httpx.TimeoutException:
            logger.warning("요약 생성 시간 초과 - 기존 요약 유지")
            return old_summary
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패 (요약) - 기존 요약 유지")
            return old_summary
        except Exception as e:
            logger.error("요약 생성 중 오류: %s - 기존 요약 유지", e)
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
        except httpx.TimeoutException:
            logger.warning("JSON 생성 시간 초과")
            return None
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패 (JSON 생성)")
            return None
        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패 - 모델 응답 형식이 올바르지 않음")
            return None
        except Exception as e:
            logger.error("JSON 생성 중 알 수 없는 오류: %s", e)
            return None

    async def generate_enemy_concept(self, player_state: PlayerState, boss: bool = False) -> Optional[dict]:
        """현재 이야기 맥락에 어울리는 독창적 몬스터를 AI가 창작"""
        story = player_state.story_summary or "모험이 막 시작되었다."

        if boss:
            role = "이 지역에 군림하는 위압적이고 강력한 보스 몬스터"
        else:
            role = "독창적인 몬스터"

        prompt = f"""당신은 텍스트 RPG의 몬스터 디자이너입니다.

장소: {player_state.location}
이야기 맥락: {story}

이 장소와 이야기에 어울리는 {role} 하나를 창작하세요.
유명 게임의 몬스터를 그대로 복사하지 말고 새로운 존재를 만드세요.

언어 규칙: name과 description 모두 반드시 100% 한국어로만 작성하세요.
영어 단어나 알파벳을 단 한 글자도 섞지 마세요.

반드시 이 JSON 형식으로만 답하세요:
{{"name": "한국어 몬스터 이름 (2~10글자)", "description": "한국어로 된, 생김새와 분위기를 담은 한 문장"}}"""

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

이 적이 남길 법한 독창적인 {kind_kr} 하나를 창작하세요.

언어 규칙: name과 description 모두 반드시 100% 한국어로만 작성하세요.
영어 단어나 알파벳을 단 한 글자도 섞지 마세요.

반드시 이 JSON 형식으로만 답하세요:
{{"name": "한국어 {kind_kr} 이름 (2~12글자)", "description": "한국어로 된 한 문장 묘사"}}"""

        data = await self._generate_json(prompt)
        if not data:
            return None

        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()

        if not name or len(name) > 24:
            return None

        return {"name": name, "description": description[:100]}

    async def extract_story_events(self, narrative: str) -> Optional[dict]:
        """서사에서 실제 게임 상태 변화(골드/체력/아이템)를 추출

        값의 범위 제한과 적용 여부는 호출자(코드)가 결정한다.
        실패 시 None -> 서사만 출력 (게임 상태 변화 없음)
        """
        prompt = f"""당신은 텍스트 RPG의 심판입니다. 아래 서사를 읽고 플레이어에게 실제로 일어난 변화만 추출하세요.

서사:
{narrative}

규칙:
1. 서사에 명확히 서술된 변화만 추출하세요 (암시나 가능성은 제외)
2. 골드를 줍거나 잃었으면 gold에 숫자 (없으면 0)
3. 다치거나 회복했으면 hp에 숫자 (다침은 음수, 없으면 0)
4. 물건을 획득했으면 item_name에 이름, item_kind에 "weapon"/"armor"/"potion" 중 하나 (없으면 null)
5. 대부분의 서사에는 아무 변화가 없습니다. 확실하지 않으면 0과 null을 쓰세요.
6. item_name은 반드시 100% 한국어로만 작성하세요. 영어 단어나 알파벳을 단 한 글자도 섞지 마세요.

반드시 이 JSON 형식으로만 답하세요:
{{"gold": 0, "hp": 0, "item_name": null, "item_kind": null}}"""

        data = await self._generate_json(prompt, timeout=20.0)
        if not data:
            return None

        try:
            return {
                "gold": int(data.get("gold") or 0),
                "hp": int(data.get("hp") or 0),
                "item_name": str(data["item_name"]).strip() if data.get("item_name") else None,
                "item_kind": str(data["item_kind"]).strip() if data.get("item_kind") else None,
            }
        except (ValueError, TypeError):
            return None

    async def generate_special_event(self, player_state: PlayerState) -> Optional[str]:
        if not player_state.inventory.has_item("map"):
            return None

        prompt = f"""당신은 텍스트 RPG의 퀘스트 생성기입니다. 이 모험가의 상태를 바탕으로 하나의 간단한 무작위 퀘스트 훅을 생성하세요 (1-2 문장).

플레이어: {player_state.name}, 레벨 {player_state.level}
현재 위치: {player_state.location}

플레이어의 현재 레벨과 위치에 맞는 퀘스트 훅을 생성하세요. 흥미롭지만 간결하게 하세요.

언어 규칙: 반드시 100% 한국어로만 작성하세요. 영어 단어나 알파벳을 단 한 글자도 섞지 마세요."""

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 100},
                }
            )
            response.raise_for_status()
            result = response.json()
            quest = result.get("response", "").strip()
            return f"[새로운 퀘스트] {quest}" if quest else None
        except httpx.TimeoutException:
            logger.warning("특수 이벤트 생성 시간 초과")
            return None
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패 (특수 이벤트)")
            return None
        except Exception as e:
            logger.error("특수 이벤트 생성 중 오류: %s", e)
            return None
