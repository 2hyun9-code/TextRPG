"""
Helper script to run the Text RPG backend server.
Serves both the API and frontend files.
"""

import uvicorn
import os
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    print("=" * 60)
    print("텍스트 RPG 백엔드 서버")
    print("=" * 60)
    print("\nOllama가 실행 중인지 확인하세요: 'ollama serve'")
    print("\n서버가 http://localhost:8000 에서 시작됩니다")
    print("프론트엔드 주소: http://localhost:8000/frontend/")
    print("\n서버를 중지하려면 Ctrl+C를 누르세요")
    print("=" * 60 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
