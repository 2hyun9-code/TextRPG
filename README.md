# 텍스트 RPG (AI 나레이터)

로컬 LLM(Ollama)이 나레이터가 되어 이야기를 만들어가는 텍스트 RPG 웹 게임.

시작은 모두 같은 서장(프롤로그)에서 출발하지만, 플레이어의 선택이 AI의 기억에 쌓이면서
중반부터는 매번 완전히 다른 이야기가 됩니다. 몬스터와 전리품도 AI가 이야기 맥락에 맞춰
즉석에서 창작합니다.

## 핵심 특징

- **AI 나레이터** — 자유 텍스트로 행동을 입력하면 AI가 결과를 서술 (스트리밍으로 실시간 표시)
- **고정 서장 + 자유 전개** — 직업별 프롤로그로 시작, 이후는 선택에 따라 이야기가 갈라짐
- **3계층 기억 시스템** — 최근 대화(원문) + 증분 요약(병합) + 게임 상태로 AI의 망각 최소화
- **AI 동적 생성** — 몬스터/전리품의 이름과 묘사는 AI가 창작, 스탯은 코드가 레벨 공식으로 보장
- **RPG 시스템** — 직업 5종, 전투/보스전, 레벨업, 상점, 인벤토리/장비, 퀘스트 3종, 지역 이동, 여관
- **순수 텍스트 UI** — 검은 배경 + 흰 테두리, 이모지/이미지 없음

## 빠른 시작

```bash
# 1. Ollama 설치 후 모델 받기 (최초 1회)
ollama pull gemma2:2b

# 2. 의존성 설치
pip install -r backend/requirements.txt

# 3. 서버 실행
cd backend
python run.py

# 4. 브라우저에서 접속
# http://localhost:8000/frontend/
```

자세한 내용은 [QUICKSTART.md](QUICKSTART.md) 참고.

## 문서

| 문서 | 내용 |
|---|---|
| [QUICKSTART.md](QUICKSTART.md) | 설치, 실행, 환경변수, 문제 해결 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 구조, 기억 시스템, API 목록 |
| [EXTENDING.md](EXTENDING.md) | 아이템/적/지역/직업 추가 방법 |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 전체 기능 요약, 알려진 한계 |

## 기술 스택

- **백엔드**: Python, FastAPI, Pydantic, httpx
- **AI**: Ollama (기본 모델 gemma2:2b, 환경변수로 교체 가능)
- **프론트엔드**: 순수 HTML/CSS/JavaScript (프레임워크 없음)
- **저장**: JSON 파일 (원자적 저장 + 백업 자동 복구)

## 프로젝트 구조

```
TextRPG/
├── backend/
│   ├── main.py           # FastAPI 서버, 게임 로직, API 엔드포인트
│   ├── models.py         # PlayerState, Item, Enemy, Quest 등 데이터 모델
│   ├── ollama_client.py  # AI 연동 (서사 생성, 요약, 몬스터/아이템 창작)
│   ├── items_db.py       # 아이템 정의, 상점 재고
│   ├── enemies_db.py     # 적 템플릿, 동적 몬스터 스탯 공식
│   ├── story.py          # 고정 프롤로그 (직업별 서장)
│   ├── run.py            # 서버 실행 스크립트
│   └── player_state.json # 세이브 파일 (자동 생성)
└── frontend/
    ├── index.html        # 게임 화면 (채팅 + 사이드 패널)
    ├── script.js         # UI 로직, API 통신, 스트리밍 렌더링
    └── style.css         # 흑백 테마
```
