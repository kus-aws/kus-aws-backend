from __future__ import annotations

import os
import json
import time
import uuid
import logging
from typing import List, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mangum import Mangum
import boto3

# -------------------------------------------------


load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_CONVERSATION_TABLE_NAME = os.getenv("DYNAMODB_CONVERSATION_TABLE_NAME", "ChatbotConversations")
DYNAMODB_FAQ_TABLE_NAME = os.getenv("DYNAMODB_FAQ_TABLE_NAME", "ChatbotFAQs")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")

# -------------------------------------------------
# AWS 클라이언트
# -------------------------------------------------
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# -------------------------------------------------
# 로깅
# -------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # 기본 로깅 레벨을 INFO로 설정

# -------------------------------------------------
# FastAPI 앱 & CORS
# -------------------------------------------------
app = FastAPI(
    title="kus-aws-backend",
    description="FastAPI backend for AI tutor (AWS Bedrock + DynamoDB + Lambda/Mangum)",
    version="1.0.0",
)

# CORS: 데모 기본값(*)
origins_env = os.getenv("CORS_ORIGINS", "*")
allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
# 브라우저 정책: '*' 와 credentials 동시 사용 불가 → 자동 보정
if allow_origins == ["*"] and allow_credentials:
    logger.warning("CORS: allow_origins=['*']와 allow_credentials=True는 함께 사용할 수 없습니다. allow_credentials를 False로 설정합니다.")
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Pydantic 모델
# -------------------------------------------------
class ChatRequest(BaseModel):
    userQuestion: str
    major: str
    subField: str
    conversationId: Optional[str] = None  # 없으면 새 대화 시작

class ChatResponse(BaseModel):
    aiResponse: str
    conversationId: str

class FAQResponse(BaseModel):
    faqs: List[Dict[str, str]]

# -------------------------------------------------
# 유틸 함수
# -------------------------------------------------
def _build_prompt(major: str, sub_field: str, history_items: List[Dict], user_question: str) -> str:
    """히스토리 + 시스템 지시문을 합쳐 Bedrock 입력 텍스트 생성."""
    system_prompt = (
        f"당신은 {major} 분야의 {sub_field}를 가르치는 전문 AI 튜터입니다. "
        "간결하고 명확하게 설명하며, 질문에 대한 답변을 제공하고 추가 질문을 유도하여 "
        "사용자의 학습을 돕습니다. 사용자의 질문에 맞춰 상세하게 설명해주세요."
    )

    lines = [system_prompt, ""]
    for item in history_items:
        
        role = item["role"]["S"]
        content = item["content"]["S"]
        if role == "user":
            lines.append(f"Human: {content}")
        else:
            lines.append(f"Assistant: {content}")

    lines.append(f"Human: {user_question}")
    lines.append("Assistant:")
    return "\n".join(lines)

def _read_bedrock_text(resp) -> str:
    """Bedrock invoke_model 응답에서 텍스트 안전 추출."""
    try:
        body_raw = resp["body"].read().decode("utf-8")
        data = json.loads(body_raw)
        return data["results"][0]["outputText"]
    except Exception as e:
        logger.exception("Bedrock 응답 파싱 오류 발생")
        raise HTTPException(status_code=502, detail=f"LLM 응답 파싱 실패: {e}")

# -------------------------------------------------
# 엔드포인트
# -------------------------------------------------
@app.get("/health", summary="헬스 체크")
def health():
    logger.info("Health check endpoint called.")
    return "ok" 

@app.get("/api/v1/echo", summary="쿼리 파라미터 에코")
def echo(q: str = Query("hello", description="반환할 문자열")):
    logger.info(f"Echo endpoint called with query: {q}")
    return {"echo": q}

@app.post("/chat", response_model=ChatResponse, summary="챗봇 대화")
async def chat_with_bot(req: ChatRequest):
    """
    - DynamoDB 스키마 가정: Partition Key=userId(S), Sort Key=timestamp(N)
    """
    conversation_id = req.conversationId or str(uuid.uuid4())
    user_question = req.userQuestion
    major = req.major
    sub_field = req.subField
    
    logger.info(f"Chat request received for conversationId: {conversation_id}")

    try:
        # 1) 기존 대화 조회 (오래된 순)
        hist_response = dynamodb.query(
            TableName=DYNAMODB_CONVERSATION_TABLE_NAME,
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": {"S": conversation_id}},
            ScanIndexForward=True, # 오래된 대화부터 가져옴
        )
        history_items = hist_response.get("Items", [])
        logger.info(f"Retrieved {len(history_items)} history items for conversation: {conversation_id}")

        # 2) 프롬프트 구성
        prompt = _build_prompt(major, sub_field, history_items, user_question)
        logger.debug(f"Bedrock prompt: {prompt}")

        # 3) Bedrock 호출
        payload = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 2000,
                "stopSequences": [],
                "temperature": 0.7,
                "topP": 0.9,
            },
        }
        llm_resp = bedrock_runtime.invoke_model(
            body=json.dumps(payload).encode("utf-8"),
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
        )
        ai_response = _read_bedrock_text(llm_resp)
        logger.info(f"Bedrock response generated for conversation: {conversation_id}")

        # 4) 대화 저장 (user → assistant)
        now = time.time()
        # 사용자 질문 저장
        dynamodb.put_item(
            TableName=DYNAMODB_CONVERSATION_TABLE_NAME,
            Item={
                "userId": {"S": conversation_id},  # Partition Key는 conversationId
                "timestamp": {"N": str(now)},     # Sort Key는 timestamp
                "role": {"S": "user"},
                "content": {"S": user_question},
                "major": {"S": major},
                "subField": {"S": sub_field},
                # "conversationId": {"S": conversation_id}, # userId와 동일하므로 제거 (redundant)
            },
        )
        # AI 답변 저장
        dynamodb.put_item(
            TableName=DYNAMODB_CONVERSATION_TABLE_NAME,
            Item={
                "userId": {"S": conversation_id},  # Partition Key는 conversationId
                "timestamp": {"N": str(now + 0.001)}, # timestamp 충돌 방지
                "role": {"S": "assistant"},
                "content": {"S": ai_response},
                "major": {"S": major},
                "subField": {"S": sub_field},
                # "conversationId": {"S": conversation_id}, # userId와 동일하므로 제거 (redundant)
            },
        )
        logger.info(f"Conversation history saved for conversation: {conversation_id}")

        return ChatResponse(aiResponse=ai_response, conversationId=conversation_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"챗봇 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"챗봇 처리 중 오류 발생: {e}")

@app.get("/faq", response_model=FAQResponse, summary="FAQ 조회")
async def get_faqs(subField: str = Query(..., description="조회할 세부 분야")):
    """
    지정된 세부 분야에 대한 FAQ 목록을 DynamoDB에서 조회하여 반환합니다.
    """
    logger.info(f"FAQ request received for subField: {subField}")
    try:
        # 'ChatbotFAQs' 테이블에서 subField를 기준으로 FAQ 조회
        resp = dynamodb.query(
            TableName=DYNAMODB_FAQ_TABLE_NAME,
            KeyConditionExpression="subField = :sf",
            ExpressionAttributeValues={":sf": {"S": subField}},
        )
        faqs = [
            {"question": it["question"]["S"], "answer": it["answer"]["S"]}
            for it in resp.get("Items", [])
        ]
        logger.info(f"Retrieved {len(faqs)} FAQs for subField: {subField}")
        return FAQResponse(faqs=faqs)
    except Exception as e:
        logger.exception(f"FAQ 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"FAQ 조회 중 오류 발생: {e}")

# -------------------------------------------------
# Lambda 핸들러 (AWS)
# -------------------------------------------------
handler = Mangum(app)

# -------------------------------------------------
# 로컬 실행 main()
# -------------------------------------------------
def main():
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting local server on http://0.0.0.0:{port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()


