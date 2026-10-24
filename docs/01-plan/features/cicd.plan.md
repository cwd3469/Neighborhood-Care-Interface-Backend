# Plan: cicd

> GitHub Actions CI/CD 정비 — 현 프로젝트 기준 재정비

- **Feature**: cicd
- **Date**: 2026-10-16
- **Phase**: Plan

---

## Executive Summary

| 관점 | 내용 |
|------|------|
| Problem | 기존 CI/CD 파일이 구 프로젝트(`Fhir-Style-Builder`) 기준으로 작성되어 있어 현 프로젝트에 적용 불가 |
| Solution | GitHub Actions `deploy.yml`을 현 프로젝트에 맞게 수정 — EC2 경로·서비스명·헬스체크 수정 |
| Function UX Effect | `develop → main` 머지 시 EC2에 자동 배포, 팀이 수동 SSH 접속 없이 배포 완료 |
| Core Value | 안정적인 자동 배포 파이프라인으로 배포 실수 방지 및 개발 속도 향상 |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| WHY | 수동 배포 과정에서 실수 발생 가능성 제거, 반복 작업 자동화 |
| WHO | 백엔드 개발자 — `develop` 브랜치에서 개발 후 `main` PR 머지 |
| RISK | EC2 SSH 키·호스트 정보가 GitHub Secrets에 없으면 배포 실패 |
| SUCCESS | `main` push 시 자동으로 EC2에 최신 코드 배포 완료 |
| SCOPE | `.github/workflows/deploy.yml` 수정 1개 파일. Jenkinsfile은 별도 처리 |

---

## 1. 요구사항

### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-01 | `main` 브랜치 push(develop 머지 포함) 시 자동 배포 트리거 | 필수 |
| FR-02 | EC2 서버 접속 → 최신 코드 pull → Docker 재빌드·재시작 | 필수 |
| FR-03 | 배포 후 컨테이너 실행 확인 (헬스체크) | 필수 |
| FR-04 | `.env` 파일은 EC2 서버에 이미 존재 (Secrets 직접 주입 아님) | 필수 |
| FR-05 | 실패 시 GitHub Actions UI에서 원인 확인 가능 | 선택 |

### 비기능 요구사항

- 도구: GitHub Actions만 사용 (Jenkins 미사용)
- EC2 접속 정보는 GitHub Secrets에 저장: `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `EC2_PORT`
- EC2의 프로젝트 경로 Secret: `EC2_DEPLOY_PATH` (예: `~/systemNeighborhoodSeniorCare/backend`)

---

## 2. 현재 상태 분석

### 기존 `deploy.yml` 문제점

```yaml
# 문제 1: 경로가 구 프로젝트명
cd ~/Fhir-Style-Builder

# 문제 2: 헬스체크가 구 서비스명
docker ps | grep fhir

# 문제 3: 배포 실패 시 처리 없음 (실패해도 성공 표시 가능)
```

### docker-compose.yml 서비스명

```yaml
services:
  app:    ← 헬스체크 시 grep 대상
  db:
```

---

## 3. 변경 범위

| 파일 | 변경 내용 |
|------|-----------|
| `.github/workflows/deploy.yml` | 전체 수정 — 경로·서비스명·헬스체크·실패처리 |
| `Jenkinsfile` | 삭제 또는 유지 (GitHub Actions만 사용) |

---

## 4. 목표 워크플로우

```
develop 브랜치 개발
    ↓
main PR 생성 + 머지
    ↓
GitHub Actions 트리거 (push to main)
    ↓
EC2 SSH 접속
    ↓
git pull origin main
    ↓
docker compose down
docker compose up -d --build
    ↓
docker ps | grep app → 성공 확인
    ↓
배포 완료 / 실패 시 GitHub UI에서 확인
```

---

## 5. GitHub Secrets 필요 목록

| Secret 이름 | 설명 | 예시 |
|-------------|------|------|
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 | `13.125.xxx.xxx` |
| `EC2_USER` | EC2 접속 사용자명 | `ubuntu` |
| `EC2_SSH_KEY` | EC2 PEM 키 내용 (전체) | `-----BEGIN RSA...` |
| `EC2_PORT` | SSH 포트 (기본 22) | `22` |
| `EC2_DEPLOY_PATH` | EC2 내 프로젝트 경로 | `~/systemNeighborhoodSeniorCare/backend` |

---

## 6. 리스크

| 리스크 | 영향도 | 대응 |
|--------|--------|------|
| EC2_DEPLOY_PATH Secret 미설정 | 높음 | 플랜 문서에 필수 항목 명시 |
| `.env` 파일이 EC2에 없을 경우 | 높음 | Docker 빌드 실패 → EC2에 `.env` 사전 배치 필수 |
| `docker compose` 권한 문제 | 중 | EC2 사용자를 docker group에 추가 필요 |
| main 직접 push (리뷰 없이) | 낮 | GitHub Branch Protection Rules 설정 권고 |

---

## 7. 성공 기준

- [ ] SC-01: `main` push 시 GitHub Actions가 자동 트리거됨
- [ ] SC-02: EC2에 SSH 접속 후 최신 코드 pull 성공
- [ ] SC-03: `docker compose up -d --build` 성공
- [ ] SC-04: `docker ps | grep app` 결과로 컨테이너 실행 확인
- [ ] SC-05: 실패 시 GitHub Actions UI에서 어떤 단계에서 실패했는지 확인 가능
