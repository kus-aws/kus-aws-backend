# kus-aws-backend

FastAPI 기반의 백엔드 리포지토리입니다. 기본 엔드포인트로 `/health`와 `/api/v1/echo`를 제공합니다.

## 요구사항
- Python ≥ 3.10

## 빠른 시작
1) 가상환경 생성 및 활성화
```
python -m venv .venv
source .venv/bin/activate
```

2) 의존성 설치
```
pip install --upgrade pip
pip install -r requirements.txt
```

3) 환경 변수 설정
- `.env.example`를 복사하여 `.env` 생성
- 주요 키
  - `PORT`: 개발 서버 포트 (예: `8000`)
  - `ALLOWED_ORIGINS`: 운영/스테이징 허용 오리진(쉼표 구분, 예: `https://app.example.com,https://admin.example.com`)
  - `ALLOWED_METHODS`(옵션): 허용 메서드(쉼표 구분, 기본 `*`)
  - `ALLOWED_HEADERS`(옵션): 허용 헤더(쉼표 구분, 기본 `*`)

4) 개발 서버 실행
```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 의존성(requirements.txt)
- boto3
- fastapi
- mangum
- python-dotenv
- uvicorn[standard]

## 엔드포인트
- `GET /health`: 단순 헬스 체크({"status":"ok"})
- `GET /api/v1/echo?q=hello`: 쿼리 파라미터 `q`를 그대로 반환

## CORS
- 현재 데모 목적상 `*` 오리진을 허용합니다. 운영 환경에서는 특정 오리진으로 제한하세요.

## AWS 메모
- 리전: us-east-1
- Access Key 발급 금지 → 인스턴스/람다는 역할(Role) 사용
  - EC2: `SafeInstanceProfileForUser-{username}`
  - Lambda: `SafeRoleForUser-{username}`
- S3 버킷 네이밍: username 접두 필수

## AWS Lambda 배포 (FastAPI + Mangum)

이 프로젝트는 AWS Lambda에서 동작하도록 Mangum으로 래핑되어 있습니다. 핸들러는 `app.main.handler` 입니다.

### Local Test
- Uvicorn으로 로컬 실행:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- 기대 응답:
  - `GET http://localhost:8000/health` → `{ "status": "ok" }`
  - `GET http://localhost:8000/api/v1/echo?q=hello` → `{ "echo": "hello" }`

### Remote Healthcheck
- API Gateway(HTTP API) 생성 후 Invoke URL 예시:
  - 스테이지 `$default`: `https://<api-id>.execute-api.us-east-1.amazonaws.com/health`
  - 스테이지 `prod`: `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/health`
- 주의: 스테이지에 따라 경로 접두가 다릅니다(`$default`는 없음, `prod`는 `/prod`).

### Lambda 패키지 빌드
- venv 의존 없이 원샷 빌드:
```bash
chmod +x scripts/build_lambda.sh
./scripts/build_lambda.sh
```
- 산출물: `lambda.zip` (의존성 + `app/` 포함)

### 콘솔에서 Lambda 생성 (us-east-1)
1. AWS Console → Lambda → Create function
2. Author from scratch
   - Name: `kus-aws-backend`
   - Runtime: `Python 3.10`
   - Architecture: `x86_64`
   - Permissions → Choose existing role: `SafeRoleForUser-{username}`
   - Create function
3. 코드 업로드
   - Upload from → `.zip file` → `lambda.zip` 업로드
4. 핸들러 설정
   - Handler: `app.main.handler`
5. Basic settings
   - 메모리/타임아웃 필요에 맞게 설정 (예: 512 MB, 15 sec)
6. Save and Deploy

### API Gateway (HTTP API)
1. Add trigger → API Gateway → Create an API → HTTP API (not REST)
2. Security: `Open`(데모) 또는 필요한 인증 구성
3. CORS: 기본값 활성화(데모). 운영 환경에서는 허용 오리진을 제한하세요.

### 콘솔 수동 배포(해커톤 규정)
1. 위 "Lambda 패키지 빌드"로 생성된 `lambda.zip` 업로드
2. 런타임: Python 3.10, 핸들러: `app.main.handler`
3. 역할(Role): `SafeRoleForUser-{username}` 선택
4. 트리거: API Gateway(HTTP API) 추가, 라우트 `/health`, `/api/v1/echo` 자동 연결 확인
5. CORS: 데모는 `*` 허용, 운영은 Amplify 도메인만 허용하도록 수정
6. 배포 후 Invoke URL로 원격 헬스체크 수행(스테이지 경로 주의)

### 보안/운영 메모
- Mangum 핸들러: `handler = Mangum(app)`
- CORS: 데모는 `*` 허용. 운영/스테이징에서는 환경 변수 `ALLOWED_ORIGINS` 사용(쉼표 구분, 예: `https://a.com,https://b.com`).
- 비밀정보는 코드에 포함하지 말고, 환경 변수/Parameter Store/Secrets Manager를 사용하세요.

## CI (옵션)
- GitHub Actions 수동 실행(`workflow_dispatch`): `.github/workflows/build-lambda.yml`
- 작업: Python 3.10 설정 → `scripts/build_lambda.sh` 실행 → `lambda.zip` 아티팩트 업로드

## 진행 상황
- FastAPI + Mangum 핸들러 노출(`app.main.handler`)
- `GET /health` JSON 응답: `{ "status":"ok" }`
- `requirements.txt` 정리(`mangum` 포함)
- 패키징 스크립트 추가: `scripts/build_lambda.sh`
- 배포 가이드 통합(`README_LAMBDA.md` → `README.md`)
- `lambda.zip` 빌드 검증(약 22MB)
- echo 응답 스키마 표준화: `{ "echo": "..." }`
- CORS 운영 설정 도입: `ALLOWED_ORIGINS`(쉼표 구분)
- 환경변수 템플릿 추가: `.env.example`(PORT, ALLOWED_ORIGINS)
- CI(workflow_dispatch) 추가: 빌드만 수행, `lambda.zip` 아티팩트 업로드(배포 자동화 금지)

## 남은 태스크
- 운영 CORS 제한(허용 오리진/메서드 구체화)
- Lambda 환경변수 `ALLOWED_ORIGINS` 운영값 설정 및 검증
- API Gateway HTTP API 고도화(커스텀 도메인/스테이지/로깅)
- IaC 도입(SAM/CloudFormation/CDK)으로 배포 자동화(규정 허용 시)
- CI 확장: 테스트/린트/보안 스캔 및 커버리지 ≥ 80%, 아티팩트 보존
- 의존성 버전 고정 및 보안 스캔(pip-tools/Dependabot)
- 관측성: 구조화 로그/메트릭/트레이싱(OpenTelemetry 등)
- 에러 처리/입력 검증 보강(보안 가드레일 강화)
- 환경 변수/비밀값 관리 표준화(SSM Parameter Store / Secrets Manager)
