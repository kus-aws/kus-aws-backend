# KUS AWS Backend

FastAPI + Mangum을 사용한 AWS Lambda 백엔드 서비스

## 설치 및 실행

### 1. 가상환경 생성 및 활성화
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 또는
.venv\Scripts\activate  # Windows
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```bash
# AWS 설정
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# Bedrock 설정
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# CORS 설정 (운영 환경에서 사용)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ALLOWED_METHODS=GET,POST,OPTIONS
ALLOWED_HEADERS=Content-Type,Authorization,x-client-request-id

# 서버 설정
PORT=8000
```

### 4. 로컬 실행
```bash
python -m app.main
```

### 5. 테스트 실행
```bash
pytest tests/
```

## API 엔드포인트

### POST /chat
메인 AI 응답을 생성합니다.

**요청:**
```json
{
  "userQuestion": "연쇄법칙이 뭐야?",
  "major": "수학",
  "subField": "미적분학",
  "followupMode": "never",
  "suggestCount": 0
}
```

**응답:**
```json
{
  "aiResponse": "연쇄법칙은...",
  "conversationId": "uuid-string",
  "suggestions": []
}
```

### POST /suggestions
후속 질문 제안을 생성합니다.

**요청:**
```json
{
  "conversationId": "uuid-string",
  "major": "수학",
  "subField": "미적분학",
  "suggestCount": 3
}
```

**응답:**
```json
{
  "suggestions": [
    "미분의 기하학적 의미는?",
    "적분과의 관계는?",
    "실생활 응용 예시는?"
  ]
}
```

### GET /chat/stream
스트리밍 채팅 응답 (선택사항)

**쿼리 파라미터:**
- `question`: 질문
- `major`: 전공 분야
- `sub_field`: 세부 분야

## 테스트

### cURL 예시

#### 메인 답변 생성
```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"userQuestion":"연쇄법칙이 뭐야?","major":"수학","subField":"미적분학","followupMode":"never","suggestCount":0}' \
  http://localhost:8000/chat
```

#### 제안 생성
```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"conversationId":"<위에서 받은 CID>","major":"수학","subField":"미적분학","suggestCount":3}' \
  http://localhost:8000/suggestions
```

## 배포

### Lambda 패키징
```bash
./scripts/build_lambda.sh
```

### AWS Lambda 배포 (콘솔 수동 배포)

#### 1. Lambda 함수 생성
- AWS Console → Lambda → Create function
- Author from scratch
- Name: `kus-aws-backend`
- Runtime: `Python 3.10`
- Architecture: `x86_64`
- Permissions → Choose existing role: `SafeRoleForUser-{username}`
- Create function

#### 2. 코드 업로드
- Code → Upload from → `.zip file` → `lambda.zip` 업로드
- Runtime settings → Edit
- Handler: `app.main.handler`
- Deploy

#### 3. 환경 변수 설정
- Configuration → Environment variables → Edit
- 다음 변수들을 추가:
  - `AWS_REGION`: `us-east-1`
  - `BEDROCK_MODEL_ID`: `anthropic.claude-3-sonnet-20240229-v1:0`
  - `ALLOWED_ORIGINS`: `https://<your-amplify-domain>` (운영 환경)
- Save → Deploy

#### 4. API Gateway 연결
- Add trigger → API Gateway → Create an API → HTTP API
- Security: `Open` (데모) 또는 필요한 인증 구성
- CORS: 기본값 활성화 (데모)
- 라우트 자동 연결 확인 (`/chat`, `/suggestions`, `/health`)

#### 5. IAM 권한 설정
Lambda 실행 역할에 다음 권한이 필요합니다:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
        }
    ]
}
```

### 환경 변수 설정
Lambda 함수에서 다음 환경 변수를 설정하세요:
- `AWS_REGION`
- `BEDROCK_MODEL_ID`
- `ALLOWED_ORIGINS` (운영 환경)

## 아키텍처

- **FastAPI**: 웹 프레임워크
- **Mangum**: Lambda 어댑터
- **Bedrock**: AI 모델 서비스
- **Pydantic**: 데이터 검증
- **boto3**: AWS SDK

## 성능 요구사항

- **/chat p95**: ≤ 20~22초
- **전체 타임아웃**: 29초 (Lambda + API Gateway)
- **504 에러**: 드물게 허용 (모델 지연)
- **500 에러**: 0% (절대 허용 불가)

## 보안

- CORS 설정으로 허용된 도메인만 접근 가능
- PII 정보는 로깅에서 제외
- 클라이언트 요청 ID로 요청 추적
- AWS IAM 권한으로 Bedrock 접근 제어

## 운영 체크리스트

### 배포 전 확인사항
- [ ] 모든 테스트 통과 (`pytest tests/`)
- [ ] Lambda 패키징 성공 (`./scripts/build_lambda.sh`)
- [ ] 환경 변수 설정 완료
- [ ] IAM 권한 설정 완료

### 배포 후 확인사항
- [ ] Lambda 함수 정상 동작
- [ ] API Gateway 엔드포인트 접근 가능
- [ ] `/health` 엔드포인트 200 응답
- [ ] `/chat` 엔드포인트 정상 동작
- [ ] `/suggestions` 엔드포인트 정상 동작
- [ ] CORS 설정 확인
- [ ] 로깅 정상 동작

### 모니터링
- [ ] CloudWatch 로그 확인
- [ ] 응답 시간 모니터링 (p95 ≤ 22초)
- [ ] 에러율 모니터링 (500 에러 0%)
- [ ] 타임아웃 발생률 모니터링 (504 에러 드물게)

## 문제 해결

### 일반적인 문제들

#### 1. Bedrock 권한 오류
- Lambda 실행 역할에 `bedrock:InvokeModel` 권한 확인
- 리전이 `us-east-1`인지 확인

#### 2. CORS 오류
- `ALLOWED_ORIGINS` 환경 변수 설정 확인
- API Gateway CORS 설정 확인

#### 3. 타임아웃 오류
- Lambda 타임아웃 설정 (권장: 25초)
- Bedrock 모델 응답 시간 모니터링

#### 4. 메모리 부족
- Lambda 메모리 설정 증가 (권장: 512MB 이상)
- 응답 크기 제한 확인
