# 네이버 부동산 조사 포탈 프런트엔드

## 한국어 안내

React, TypeScript, Vite와 Tailwind CSS로 구현된 포탈 화면이다. 저장소 루트의 통합 실행 스크립트를 사용하는 것이 기본 방식이다.

### 권장 실행

Windows PowerShell에서 저장소 루트를 기준으로 실행한다.

```powershell
.\scripts\setup-local.ps1
.\scripts\start.ps1 -Mode local
```

Docker로 실행하려면 `backend/.env.example`을 `backend/.env`로 복사한 뒤 다음 명령을 사용한다.

```powershell
.\scripts\start.ps1 -Mode docker
```

### 프런트엔드만 실행

Node.js 22 LTS와 npm 패키지가 준비된 상태에서 실행한다.

```powershell
Set-Location .\frontend
npm run dev -- --host 127.0.0.1 --port 42880 --strictPort
```

개발 서버는 `http://127.0.0.1:42880`에서 열린다. `/api` 요청은 Vite proxy를 통해 `http://127.0.0.1:42881`의 FastAPI로 전달되므로 API를 별도로 실행해야 한다.

Docker에서는 Nginx가 정적 빌드 결과를 제공하고 `/api`를 내부 `api:8000` 서비스로 전달한다. 전체 서비스의 공식 구성은 저장소 루트의 `docker-compose.production.yml`이다.

---

# Frontend Runtime Contract

## AI Reference

- Required Node.js version: `>=22 <23`.
- Canonical Windows entry point: `scripts/start.ps1 -Mode local|docker`.
- Local Vite host and port: `127.0.0.1:42880`.
- Local `/api` proxy target: `http://127.0.0.1:42881`.
- Docker serves the production build through Nginx and proxies `/api` to `api:8000`.
- The canonical full-service Compose file is `docker-compose.production.yml` at the repository root.
