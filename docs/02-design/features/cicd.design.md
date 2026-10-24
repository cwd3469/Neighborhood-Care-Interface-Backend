# Design: cicd

> GitHub Actions CI+CD 분리 — Option B

- **Feature**: cicd
- **Date**: 2026-10-16
- **Architecture**: Option B — CI/CD 분리
- **Phase**: Design

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| WHY | 수동 배포 제거, develop→main 머지 시 자동 배포 및 PR 품질 검증 |
| WHO | 백엔드 개발자 — develop 브랜치에서 개발 후 main PR |
| RISK | EC2_DEPLOY_PATH Secret 미설정 시 배포 실패 |
| SUCCESS | main push 시 자동 배포 완료, PR 시 Python 문법 오류 조기 감지 |
| SCOPE | `.github/workflows/ci.yml` 신규, `.github/workflows/deploy.yml` 수정 |

---

## 1. 아키텍처 결정

**선택: Option B — CI와 CD 분리**

| 워크플로우 | 트리거 | 목적 |
|-----------|--------|------|
| `ci.yml` | PR → `main` | Python 문법·의존성 검증 (코드 품질 게이트) |
| `deploy.yml` | push → `main` | EC2 자동 배포 |

**근거:**
- CI는 PR 단계에서 문제를 조기에 감지 → main 오염 방지
- CD는 merge 후에만 실행 → 불필요한 배포 트리거 없음
- 두 파일 독립적으로 관리 가능

---

## 2. `ci.yml` 설계

### 트리거
```yaml
on:
  pull_request:
    branches:
      - main
```

### 전체 구조

```yaml
name: CI — Python Syntax Check

on:
  pull_request:
    branches:
      - main

jobs:
  lint:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Syntax check — all Python files
        run: python -m compileall -q .

      - name: Import check — FastAPI app entry
        run: python -c "import main"
        env:
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test-secret-key
          ALGORITHM: HS256
          ACCESS_TOKEN_EXPIRE_MINUTES: 30
          ANTHROPIC_API_KEY: test-key
```

### 체크 항목

| 단계 | 내용 | 실패 시 |
|------|------|---------|
| Install dependencies | `requirements.txt` 패키지 설치 | PR merge 차단 |
| Syntax check | 전체 `.py` 파일 컴파일 오류 검출 | PR merge 차단 |
| Import check | `main.py` 임포트 성공 확인 | PR merge 차단 |

---

## 3. `deploy.yml` 설계

### 트리거
```yaml
on:
  push:
    branches:
      - main
```

### 전체 구조

```yaml
name: Deploy Backend to EC2

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          port: ${{ secrets.EC2_PORT }}
          script: |
            cd ${{ secrets.EC2_DEPLOY_PATH }}
            git pull origin main
            docker compose down
            docker compose up -d --build
            docker ps | grep app
```

### 핵심 수정 사항 (기존 대비)

| 항목 | 기존 | 변경 |
|------|------|------|
| `actions/checkout` | `@v3` | `@v4` |
| EC2 경로 | `~/Fhir-Style-Builder` | `${{ secrets.EC2_DEPLOY_PATH }}` |
| 헬스체크 | `grep fhir` | `grep app` |

---

## 4. GitHub Secrets 설정 가이드

GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 설명 | 예시 |
|-------------|------|------|
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 | `13.125.xxx.xxx` |
| `EC2_USER` | SSH 접속 사용자명 | `ubuntu` |
| `EC2_SSH_KEY` | PEM 파일 전체 내용 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `EC2_PORT` | SSH 포트 | `22` |
| `EC2_DEPLOY_PATH` | EC2 내 프로젝트 절대/홈 경로 | `~/systemNeighborhoodSeniorCare/backend` |

---

## 5. 브랜치 보호 규칙 권장 (GitHub Settings)

```
Branch: main
✅ Require a pull request before merging
✅ Require status checks to pass before merging
   → Status check: "lint" (ci.yml job name)
✅ Require branches to be up to date before merging
```

이 설정이 있어야 CI 실패 시 merge가 차단됩니다.

---

## 6. 전체 흐름

```
[개발자] develop 브랜치에서 작업
    ↓
[GitHub] main PR 생성
    ↓
[ci.yml] 자동 실행
  - Python 의존성 설치
  - 문법 검사
  - import 검사
  → 실패: PR merge 차단
  → 성공: merge 가능
    ↓
[개발자] PR merge (develop → main)
    ↓
[deploy.yml] 자동 실행
  - EC2 SSH 접속
  - git pull origin main
  - docker compose down
  - docker compose up -d --build
  - docker ps | grep app
  → 성공: 배포 완료
  → 실패: GitHub Actions 탭에서 로그 확인
```

---

## 7. 구현 파일 목록

| 파일 | 작업 | 변경량 |
|------|------|--------|
| `.github/workflows/ci.yml` | 신규 생성 | ~30줄 |
| `.github/workflows/deploy.yml` | 수정 (경로·버전·헬스체크) | ~5줄 변경 |
| `Jenkinsfile` | 삭제 (GitHub Actions만 사용) | 삭제 |

---

## 8. Implementation Guide

### 11.3 Session Guide

```
Module Map:
  module-1: ci.yml 신규 생성
  module-2: deploy.yml 수정 (3곳)
  module-3: Jenkinsfile 삭제 (선택)

단일 세션으로 전체 완료 가능
```
