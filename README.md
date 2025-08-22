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
- fastapi
- uvicorn[standard]
- boto3
- python-dotenv

## 엔드포인트
- `GET /health`: 단순 헬스 체크("ok")
- `GET /api/v1/echo?q=hello`: 쿼리 파라미터 `q`를 그대로 반환

## CORS
- 현재 데모 목적상 `*` 오리진을 허용합니다. 운영 환경에서는 특정 오리진으로 제한하세요.

## AWS 메모
- 리전: us-east-1
- Access Key 발급 금지 → 인스턴스/람다는 역할(Role) 사용
  - EC2: `SafeInstanceProfileForUser-{username}`
  - Lambda: `SafeRoleForUser-{username}`
- S3 버킷 네이밍: username 접두 필수
