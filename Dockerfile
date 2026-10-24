# Python 3.11 슬림 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 — 레이어 캐싱 활용
COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY . .

# 포트 노출 (로컬 기본값 — Render 등 PaaS는 PORT 환경변수로 포트를 지정)
EXPOSE 8000

# 서버 실행 — PORT가 있으면 그 값, 없으면 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]