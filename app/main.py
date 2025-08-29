from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mangum import Mangum
import os
import json
import uuid
import asyncio
import time
from typing import List, Optional
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError, WaiterError
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="kus-aws-backend")

# 초기 데모용 CORS: 운영 시 Amplify 도메인(예: https://<amplify-domain>)만 허용하도록 제한 필요
# 운영/스테이징에서는 환경 변수 ALLOWED_ORIGINS를 사용(쉼표 구분, 예: https://a.com,https://b.com)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if allowed_origins_env.strip() == "*" else [
    o.strip() for o in allowed_origins_env.split(",") if o.strip()
]
allowed_methods_env = os.getenv("ALLOWED_METHODS", "*")
allowed_methods: List[str] = ["*"] if allowed_methods_env.strip() == "*" else [
    m.strip() for m in allowed_methods_env.split(",") if m.strip()
]
allowed_headers_env = os.getenv("ALLOWED_HEADERS", "*")
allowed_headers: List[str] = ["*"] if allowed_headers_env.strip() == "*" else [
    h.strip() for h in allowed_headers_env.split(",") if h.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
)

# Bedrock 클라이언트 설정
bedrock_client = boto3.client(
    'bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    config=boto3.session.Config(
        connect_timeout=3,  # 연결 타임아웃 3초
        read_timeout=22,    # 읽기 타임아웃 22초 (총 25초)
        retries={'max_attempts': 1}  # 최대 1회 재시도
    )
)

# 데이터 모델
class ChatRequest(BaseModel):
    userQuestion: str = Field(..., description="사용자 질문")
    major: str = Field(..., description="전공 분야")
    subField: str = Field(..., description="세부 분야")
    followupMode: str = Field("never", description="후속 질문 모드")
    suggestCount: int = Field(0, description="제안 개수")

class ChatResponse(BaseModel):
    aiResponse: str = Field(..., description="AI 응답")
    conversationId: str = Field(..., description="대화 ID")
    suggestions: List[str] = Field(default_factory=list, description="제안 목록")

class SuggestionsRequest(BaseModel):
    conversationId: str = Field(..., description="대화 ID")
    major: str = Field(..., description="전공 분야")
    subField: str = Field(..., description="세부 분야")
    suggestCount: int = Field(3, description="제안 개수")

class SuggestionsResponse(BaseModel):
    suggestions: List[str] = Field(..., description="제안 목록")

class HealthResponse(BaseModel):
    status: str

class EchoResponse(BaseModel):
    echo: str

# Bedrock 호출 함수
async def invoke_bedrock(prompt: str, max_tokens: int = 1000) -> str:
    """Bedrock 모델을 호출하여 응답을 생성합니다."""
    try:
        # Claude 3 Sonnet 모델 사용 (환경변수로 설정 가능)
        model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
        
        if 'claude' in model_id:
            # Claude 모델용 프롬프트 형식
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        else:
            # 다른 모델용 기본 형식
            body = {
                "prompt": prompt,
                "max_tokens": max_tokens
            }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        
        if 'claude' in model_id:
            return response_body['content'][0]['text']
        else:
            return response_body.get('completion', '')
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ThrottlingException':
            logger.warning("Bedrock throttling occurred")
            raise HTTPException(status_code=429, detail="Service temporarily unavailable")
        elif error_code == 'ModelTimeoutException':
            logger.error("Bedrock timeout occurred")
            raise HTTPException(
                status_code=504, 
                detail={"error": "bedrock_timeout", "message": "AI model response timeout"}
            )
        else:
            logger.error(f"Bedrock error: {error_code}")
            raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error in Bedrock: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# 채팅 응답 생성
async def generate_chat_response(request: ChatRequest) -> ChatResponse:
    """사용자 질문에 대한 AI 응답을 생성합니다."""
    conversation_id = str(uuid.uuid4())
    
    # 프롬프트 구성
    prompt = f"""당신은 {request.major} 분야의 {request.subField} 전문가입니다.
사용자의 질문에 대해 명확하고 정확하게 답변해주세요.

질문: {request.userQuestion}

답변:"""
    
    try:
        ai_response = await invoke_bedrock(prompt, max_tokens=800)
        
        return ChatResponse(
            aiResponse=ai_response,
            conversationId=conversation_id,
            suggestions=[]  # followupMode가 "never"이므로 빈 배열
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating chat response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate response")

# 제안 생성
async def generate_suggestions(request: SuggestionsRequest) -> SuggestionsResponse:
    """후속 질문 제안을 생성합니다."""
    # 프롬프트 구성
    prompt = f"""당신은 {request.major} 분야의 {request.subField} 전문가입니다.
이전 대화를 바탕으로 사용자가 궁금해할 만한 후속 질문 {request.suggestCount}개를 제안해주세요.

각 제안은 간결하고 구체적이어야 하며, 번호 없이 줄바꿈으로 구분해주세요.

제안:"""
    
    try:
        suggestions_text = await invoke_bedrock(prompt, max_tokens=400)
        
        # 응답을 줄바꿈으로 분리하여 제안 목록 생성
        suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
        
        # 요청된 개수만큼 반환
        suggestions = suggestions[:request.suggestCount]
        
        return SuggestionsResponse(suggestions=suggestions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")

@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """요청/응답 로깅 미들웨어"""
    start_time = time.time()
    
    # 클라이언트 요청 ID 생성 또는 추출
    client_request_id = request.headers.get('x-client-request-id', str(uuid.uuid4()))
    
    # 요청 로깅 (PII 제외)
    log_record = {
        "timestamp": time.time(),
        "client_request_id": client_request_id,
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']}
    }
    logger.info(f"Request: {json.dumps(log_record, ensure_ascii=False)}")
    
    try:
        response = await call_next(request)
        
        # 응답 로깅
        process_time = time.time() - start_time
        response_log = {
            "timestamp": time.time(),
            "client_request_id": client_request_id,
            "status_code": response.status_code,
            "process_time": round(process_time, 3),
            "headers": dict(response.headers)
        }
        logger.info(f"Response: {json.dumps(response_log, ensure_ascii=False)}")
        
        # 클라이언트 요청 ID를 응답 헤더에 포함
        response.headers['x-client-request-id'] = client_request_id
        
        return response
        
    except Exception as e:
        # 에러 로깅
        error_log = {
            "timestamp": time.time(),
            "client_request_id": client_request_id,
            "error": str(e),
            "error_type": type(e).__name__
        }
        logger.error(f"Error: {json.dumps(error_log, ensure_ascii=False)}")
        raise

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """메인 채팅 응답을 생성합니다."""
    # followupMode와 suggestCount 검증
    if request.followupMode != "never" or request.suggestCount != 0:
        raise HTTPException(
            status_code=400, 
            detail="followupMode must be 'never' and suggestCount must be 0 for /chat endpoint"
        )
    
    try:
        return await generate_chat_response(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/suggestions", response_model=SuggestionsResponse)
async def suggestions(request: SuggestionsRequest):
    """후속 질문 제안을 생성합니다."""
    try:
        return await generate_suggestions(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in suggestions endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/chat/stream")
async def chat_stream(question: str, major: str, sub_field: str):
    """스트리밍 채팅 응답 (선택사항)"""
    async def generate_stream():
        try:
            prompt = f"""당신은 {major} 분야의 {sub_field} 전문가입니다.
사용자의 질문에 대해 명확하고 정확하게 답변해주세요.

질문: {question}

답변:"""
            
            # 간단한 스트리밍 구현 (실제로는 Bedrock의 스트리밍 기능 사용)
            response = await invoke_bedrock(prompt, max_tokens=800)
            
            # 응답을 단어 단위로 분할하여 스트리밍
            words = response.split()
            for i, word in enumerate(words):
                if i > 0:
                    yield f" {word}"
                else:
                    yield word
                await asyncio.sleep(0.1)  # 100ms 지연
                
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}

@app.get("/api/v1/echo", response_model=EchoResponse)
def echo(q: str = "hello"):
    return {"echo": q}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

# AWS Lambda handler via Mangum
handler = Mangum(app)
