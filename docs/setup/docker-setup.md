# Docker 설치 및 실행 가이드

## 한국어 안내

### 1. 설치할 항목

Windows에서는 WSL 2와 Docker Desktop이 필요하다. Docker Desktop에는 이 프로젝트가 사용하는 Docker Engine, Docker CLI와 Docker Compose가 포함된다.

- [Microsoft WSL 설치 안내](https://learn.microsoft.com/windows/wsl/install)
- [Docker Desktop for Windows 설치 안내](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker Compose 설치 방식](https://docs.docker.com/compose/install/)

관리자 PowerShell에서 WSL을 설치한 뒤 Windows를 다시 시작하고 Docker Desktop을 설치한다.

```powershell
wsl --install
```

Docker Desktop을 실행한 다음 일반 PowerShell에서 설치 상태를 확인한다.

```powershell
docker version
docker compose version
```

프로젝트 스크립트는 Docker Desktop이나 WSL을 자동 설치하지 않는다.

### 2. 환경파일 준비

저장소 루트에서 예시 파일을 복사한다.

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

`backend/.env`의 `APP_RUNTIME=docker`, 데이터베이스 자격 증명, CORS와 수집 설정을 확인한다. PostgreSQL 관련 값을 바꾸면 Compose의 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`와 `DATABASE_URL`을 서로 맞춰야 한다. 이 파일은 Git에 포함되지 않는다.

### 3. 시작과 접속

```powershell
.\scripts\start.ps1 -Mode docker
```

스크립트는 Docker 실행 상태와 환경파일을 확인한 뒤 production Compose 구성을 빌드하고 시작한다.

- 포탈: `http://127.0.0.1:42880`
- API: `http://127.0.0.1:42881`
- API 문서: `http://127.0.0.1:42881/docs`

호스트 포트는 `42880`, `42881`이고 컨테이너 내부 포트는 각각 `80`, `8000`으로 유지된다.

### 4. 상태·로그·종료

```powershell
docker compose -f .\docker-compose.production.yml ps
docker compose -f .\docker-compose.production.yml logs --tail 100
docker compose -f .\docker-compose.production.yml down
```

PostgreSQL 데이터는 `postgres_data`, Redis 데이터는 `redis_data` 볼륨에 유지된다. 데이터를 보존하려면 `down -v`를 사용하지 않는다. 운영 점검과 백업·복구 절차는 `docs/operations/runbook.md`를 따른다.

---

# AI Docker Runtime Contract (English)

Install WSL 2 and Docker Desktop manually using the official links above. Confirm `docker version` and `docker compose version`, copy `backend/.env.example` to `backend/.env`, and keep `APP_RUNTIME=docker`.

Run `scripts/start.ps1 -Mode docker`. Compose exposes frontend `127.0.0.1:42880` and API `127.0.0.1:42881` while preserving container ports `80/8000`. Stop with `docker compose -f docker-compose.production.yml down`; never append `-v` unless explicit data deletion is approved. The scripts must not install Docker, modify unrelated processes, or delete persistent volumes.
