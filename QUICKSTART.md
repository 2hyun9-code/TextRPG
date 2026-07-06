# 빠른 시작 가이드

## 1. Ollama 설치 (최초 1회)

1. https://ollama.ai 에서 Ollama를 내려받아 설치
2. 기본 모델 받기:
   ```bash
   ollama pull gemma2:2b
   ```
   - 약 1.6GB, CPU만으로도 동작합니다 (GPU 불필요)
   - 다른 모델을 쓰고 싶으면 아래 "환경변수" 참고

Ollama는 설치 후 백그라운드 서비스로 자동 실행됩니다.
`ollama serve`를 직접 실행할 필요는 보통 없으며, "포트 사용 중" 오류가 나오면
이미 실행 중이라는 뜻입니다.

## 2. Python 의존성 설치 (최초 1회)

```bash
cd backend
pip install -r requirements.txt
```

## 3. 게임 서버 실행

```bash
cd backend
python run.py
```

서버가 시작되면 모델을 미리 로드(프리워밍)하므로 첫 응답도 빠릅니다.

## 4. 게임 접속

브라우저에서 열기: **http://localhost:8000/frontend/**

- 처음이면 직업 선택 → 서장(프롤로그)이 시작됩니다
- 입력창에 자유롭게 행동을 쓰면 AI 나레이터가 이야기를 이어갑니다
- 새로고침해도 최근 대화와 요약이 복원됩니다

## 환경변수 (선택)

코드 수정 없이 실행 시점에 바꿀 수 있습니다:

| 변수 | 기본값 | 용도 |
|---|---|---|
| `OLLAMA_MODEL` | `gemma2:2b` | 사용할 모델 (예: `llama2-uncensored`) |
| `OLLAMA_URL` | `http://localhost:11434` | 원격 Ollama 서버 주소 |
| `TEXTRPG_AI_GEN` | `1` | `0`이면 AI 동적 생성 끄기 (테스트용) |

```bash
# 예: 다른 모델로 실행
OLLAMA_MODEL=llama2-uncensored python run.py

# 예: 원격 Ollama 사용 (클라우드 VM 등)
OLLAMA_URL=http://192.168.0.10:11434 python run.py
```

PowerShell에서는:
```powershell
$env:OLLAMA_MODEL = "llama2-uncensored"; python run.py
```

## 문제 해결

**"나레이터가 자리를 비웠다..." 메시지가 나옴**
- Ollama가 꺼져 있습니다. Ollama 앱을 실행하거나 `ollama serve` 실행
- 게임 자체는 Ollama 없이도 동작합니다 (폴백 몬스터/메시지 사용)

**`ollama serve` 실행 시 "bind: Only one usage..." 오류**
- 이미 Ollama가 실행 중입니다. 그냥 게임을 시작하면 됩니다.

**응답이 너무 느림**
- 더 작은 모델 사용: `gemma2:2b`가 기본이며 가장 가볍습니다
- 스트리밍으로 첫 글자는 1초 내에 표시되지만, 전체 생성은 CPU 성능에 따라 수 초 걸립니다

**AI가 가끔 영어로 답하거나 한국어가 어색함**
- 2B급 소형 모델의 한계입니다. 더 나은 품질을 원하면:
  ```bash
  ollama pull gemma2:9b
  OLLAMA_MODEL=gemma2:9b python run.py
  ```

**브라우저에 옛 화면이 보임**
- 서버가 캐시 방지 헤더를 보내지만, 안 될 경우 Ctrl+Shift+R (강력 새로고침)

**세이브 파일이 깨짐**
- 자동으로 백업(`player_state.backup.json`)에서 복구됩니다
- 둘 다 깨진 경우에만 새 게임으로 시작됩니다

## 새 게임 시작

화면 상단의 **새 게임** 버튼 → 확인 → 직업 선택.
기존 진행은 초기화됩니다.
