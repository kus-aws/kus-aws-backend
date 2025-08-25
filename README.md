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
- `.env.example`를 복사하여 `.env` 생성 (예: `PORT=8000`)

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

### 보안/운영 메모
- Mangum 핸들러: `handler = Mangum(app)`
- 현재 CORS는 데모 목적상 `*` 허용. 운영 환경에서는 제한 필요.
- 비밀정보는 코드에 포함하지 말고, 환경 변수/Parameter Store/Secrets Manager를 사용하세요.
