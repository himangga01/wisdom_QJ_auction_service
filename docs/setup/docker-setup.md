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

`backend/.env`의 `APP_RUNTIME=docker`, `CRAWLER_CDP_URL=http://chrome:9222`, 데이터베이스 자격 증명, CORS와 수집 설정을 확인한다. `APP_RUNTIME`이 유일한 런타임 선택자다. `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`와 `DATABASE_URL`의 사용자·비밀번호·DB 이름은 서로 일치해야 한다. 이 파일은 Git에 포함되지 않는다.

`AUTH_BOOTSTRAP_TOKEN`의 예시 값은 의도적으로 실행이 거부된다. 다음과 같이 32바이트 무작위 token을 만든 뒤 출력된 64자리 값을 `backend/.env`의 예시 값과 교체한다. 이 값은 최초 관리자 설정 때만 입력하며 비밀번호처럼 보관한다.

```powershell
$tokenBytes = New-Object byte[] 32
$tokenGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$tokenGenerator.GetBytes($tokenBytes)
$tokenGenerator.Dispose()
[System.BitConverter]::ToString($tokenBytes).Replace('-', '').ToLowerInvariant()
```

`start.ps1 -Mode docker`는 `backend/.env`를 Docker Compose의 `--env-file`로 전달하므로 Compose 변수 치환과 컨테이너 환경변수가 같은 값을 사용한다. 전체 서비스의 공식 Compose 파일은 저장소 루트의 `docker-compose.production.yml`이다. `backend/docker-compose.yml`은 레거시 백엔드 개발용이며 전체 포탈 실행에 사용하지 않는다.

### 3. 시작과 접속

```powershell
.\scripts\start.ps1 -Mode docker
```

스크립트는 Docker 실행 상태와 환경파일을 확인한 뒤 production Compose 구성을 빌드하고 시작한다.

- 포탈: `http://127.0.0.1:42880`
- API: `http://127.0.0.1:42881`
- API 문서: `http://127.0.0.1:42881/docs`

호스트 포트는 `42880`, `42881`이고 컨테이너 내부 포트는 각각 `80`, `8000`으로 유지된다.

`chrome` 서비스는 비 root 사용자로 Xvfb 위에서 Google Chrome Stable을 실행한다. 프로필은 `chrome_profile:/var/lib/chrome/profile`에 영속화된다. worker는 Chrome health가 정상인 뒤 시작하지만 API는 Chrome 장애와 독립적으로 시작해 `/api/health`에서 `browser=unavailable`, `status=degraded`를 반환한다. CDP `9222`는 `expose`와 내부 `crawler_control` 네트워크만 사용하며 호스트 `ports`에 게시하지 않는다.

### 4. 상태·로그·종료

```powershell
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml ps
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml logs --tail 100
docker compose --env-file .\backend\.env -f .\docker-compose.production.yml down
```

PostgreSQL 데이터는 `postgres_data`, Redis 데이터는 `redis_data`, Chrome 세션은 `chrome_profile` 볼륨에 유지된다. 데이터를 보존하려면 `down -v`를 사용하지 않는다. `chrome_profile` 삭제·초기화는 별도 승인 없이는 하지 않는다. 운영 점검과 백업·복구 절차는 `docs/operations/runbook.md`를 따른다.

Chrome 이미지는 기본적으로 빌드 시점의 공식 Google Chrome Stable을 설치한다. 특정 패키지를 재현해야 할 때만 `backend/.env`에 공식 저장소에 현재 존재하는 `GOOGLE_CHROME_VERSION=<version>-1`과 대응하는 `CHROME_IMAGE_TAG`를 함께 지정한다. 오래되어 공식 저장소에서 제거된 버전은 기본값으로 고정하지 않는다. 별도 승인된 정적 Compose 검사, 이미지 빌드, `/json/version` 확인, `about:blank` smoke check 순서로 검증한다. `--no-sandbox`, `--disable-web-security`, privileged, host networking, stealth, fingerprint 위장, proxy 회전, CAPTCHA 우회는 허용하지 않는다.

---

# AI Docker Runtime Contract (English)

Install WSL 2 and Docker Desktop manually using the official links above. Confirm `docker version` and `docker compose version`, copy `backend/.env.example` to `backend/.env`, and keep `APP_RUNTIME=docker`. Replace the rejected `AUTH_BOOTSTRAP_TOKEN` sentinel with a cryptographically random token of at least 32 bytes. Keep `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and the credentials embedded in `DATABASE_URL` aligned.

Run `scripts/start.ps1 -Mode docker`. `APP_RUNTIME=docker` is the sole runtime selector and constrains CDP to `http://chrome:9222`. The non-root Chrome/Xvfb sidecar persists `/var/lib/chrome/profile` in `chrome_profile`; its port `9222` is internal-only. The worker and scheduler wait for Chrome health, while API startup remains independent so health can report degradation. Stop with `docker compose --env-file backend/.env -f docker-compose.production.yml down`; never append `-v` unless explicit data deletion is approved. Chrome installs the official stable package available at build time by default. Set both `GOOGLE_CHROME_VERSION` and `CHROME_IMAGE_TAG` only for an exact package that still exists in the official repository. Perform separately approved static/build/readiness/about:blank checks. Never add sandbox bypasses, host CDP publication, stealth, fingerprint spoofing, proxy rotation, or CAPTCHA bypass.
