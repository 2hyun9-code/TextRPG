# 확장 가이드

게임에 콘텐츠를 추가하는 방법. 모든 예시는 실제 코드 구조 기준입니다.

## 아이템 추가

`backend/items_db.py`의 `ITEMS_DB`에 항목 추가:

```python
"flame_sword": {
    "name": "화염검",
    "description": "칼날에 불꽃이 흐르는 검.",
    "item_type": ItemType.WEAPON,
    "effect": {"attack_bonus": 12},
    "price": 250,
},
```

- `item_type`: `WEAPON`(장착) / `ARMOR`(장착) / `CONSUMABLE`(사용) / `SPECIAL`(판매 불가)
- 무기는 `attack_bonus`, 방어구는 `defense_bonus`, 소모품은 `heal` 효과 사용
- 상점에서 팔려면 `SHOP_STOCK` 리스트에 id 추가

참고: 전리품 장비는 AI가 동적 생성하므로, DB에 추가하는 아이템은 주로 상점용입니다.

## 적(폴백 몬스터) 추가

평소에는 AI가 몬스터를 창작하지만, Ollama가 꺼져 있을 때는
`backend/enemies_db.py`의 `ENEMY_TEMPLATES`를 사용합니다:

```python
{"id": "ghost", "name": "원혼", "level": 6, "hp": 110,
 "attack": 22, "defense": 6, "xp": 140, "gold": 80},
```

드롭을 주려면 `DROP_TABLES`에 추가:

```python
"ghost": [("medium_potion", 0.25), ("oak_staff", 0.08)],
```

### 밸런스 공식 (동적 몬스터 스탯)

레벨 조정 시 참고. `enemies_db.py`에 정의:

| 스탯 | 공식 |
|---|---|
| 체력 | 20 + 레벨^1.5 × 8 |
| 공격 | 4 + 3.6 × 레벨 |
| 방어 | 1.55 × 레벨 |
| 경험치 | 20 + 4.5 × 레벨² |
| 골드 | 경험치 × (0.4 + 레벨 × 0.03) |

보스 배율: 체력 ×1.8, 공격 ×1.2, 방어 +2, 보상 ×3.

## 지역 추가

`backend/main.py`의 `LOCATIONS`에 추가:

```python
"얼어붙은 호수": {"description": "수면 아래에서 무언가 움직인다.", "can_rest": False},
```

이것만으로 이동 목록, 퀘스트 게시판(해당 지역 소탕), AI 몬스터 창작(장소 반영)에
자동 연동됩니다. 적 강함은 지역이 아닌 플레이어 레벨에 맞춰 결정되므로
레벨 범위 지정은 필요 없습니다.

## 직업 추가

세 곳을 수정합니다:

1. `backend/models.py` — `JobClass` enum에 추가 + `set_job_class()`의 `job_stats`에 스탯 정의
   + `get_effective_attack()`에 공격력 공식 + `gain_experience()`의 `growth`에 성장치
2. `backend/main.py` — `/api/game/jobs`의 직업 목록에 설명 추가
3. `backend/story.py` — `JOB_NAMES`와 `JOB_PROLOGUES`에 직업명/서장 사연 추가

## 프롤로그(서장) 수정

`backend/story.py`:

- `PROLOGUE_COMMON` — 공통 도입부 (마을, 이변, 촌장의 부탁)
- `JOB_PROLOGUES` — 직업별 사연
- `get_seed_summary()` — AI의 초기 기억에 심는 전제. 여기를 바꾸면
  나레이터가 이끄는 초반 이야기의 방향이 바뀝니다.

## 퀘스트 타입 추가

`backend/main.py` 참고 구현: `_boss_quest_offer` / `_explore_quest_offer`.

새 타입을 만들려면:

1. offer 함수 작성 (id, title, quest_type, target_count, 보상)
2. `/api/quest/available`에서 offers에 추가
3. `/api/quest/accept`에서 id 분기 처리
4. 진행 훅 연결 — 처치 계열은 `_update_quest_progress`, 이동 계열은
   `_update_explore_progress` 패턴을 참고해 해당 엔드포인트에서 호출
5. 완료 처리는 `_complete_quest(player, q, logs)` 재사용 (보상+기록 자동)

주의: 완료 조건이 실제 게임 행동과 연결되지 않는 퀘스트(예: 존재하지 않는
아이템 수집)는 영원히 완료할 수 없으므로 만들지 마세요.

## AI 모델/프롬프트 변경

- **모델 교체**: 코드 수정 없이 `OLLAMA_MODEL=모델명 python run.py`
- **나레이터 성격**: `ollama_client.py`의 `_build_system_prompt()` 지시사항 수정
- **몬스터 창작 스타일**: `generate_enemy_concept()`의 프롬프트 수정
- **요약 규칙**: `update_summary()`의 병합 규칙 수정 (보존 우선순위 등)

## 밸런스 상수 (main.py 상단)

| 상수 | 기본값 | 의미 |
|---|---|---|
| `HISTORY_TRIGGER` | 30 | 이 개수 도달 시 요약 실행 |
| `HISTORY_KEEP` | 10 | 요약 후 원문 유지 개수 |
| `MAX_HISTORY_HARD_LIMIT` | 100 | 히스토리 절대 상한 |
| `MAX_ACTIVE_QUESTS` | 5 | 동시 퀘스트 수 |
| `COMPLETED_QUESTS_CAP` | 20 | 완료 기록 보관 수 |
| `BOSS_CHANCE` | 0.10 | 사냥 시 보스 확률 |
| `BOSS_LEVEL_OFFSET` | 2 | 보스 레벨 = 플레이어 +2 |
| `BOSS_MIN_PLAYER_LEVEL` | 3 | 이 레벨 미만 보스 미등장 |
| `ENEMY_LEVEL_MIN/MAX_OFFSET` | -1 / +2 | 일반 적 레벨 범위 |

## UI 규칙

프론트엔드 수정 시 지켜야 할 프로젝트 규칙:

- 배경은 검정(#000000), 테두리는 흰색(#ffffff) — 회색조(#555~#ccc)는 보조로 허용
- **이모지/이미지 절대 사용 금지** — 순수 텍스트만
- 모든 게임 텍스트는 한국어
