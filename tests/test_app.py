import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_health_endpoint():
    """헬스 체크 엔드포인트 테스트"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_endpoint_valid_request():
    """유효한 채팅 요청 테스트"""
    request_data = {
        "userQuestion": "연쇄법칙이 뭐야?",
        "major": "수학",
        "subField": "미적분학",
        "followupMode": "never",
        "suggestCount": 0
    }
    
    response = client.post("/chat", json=request_data)
    
    # 응답 구조 검증
    assert response.status_code == 200
    data = response.json()
    assert "aiResponse" in data
    assert "conversationId" in data
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) == 0
    
    # conversationId가 UUID 형식인지 검증
    import uuid
    try:
        uuid.UUID(data["conversationId"])
    except ValueError:
        pytest.fail("conversationId is not a valid UUID")

def test_chat_endpoint_invalid_followup_mode():
    """잘못된 followupMode로 채팅 요청 시 에러 테스트"""
    request_data = {
        "userQuestion": "연쇄법칙이 뭐야?",
        "major": "수학",
        "subField": "미적분학",
        "followupMode": "always",  # 잘못된 값
        "suggestCount": 0
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 400
    assert "followupMode must be 'never'" in response.json()["detail"]

def test_chat_endpoint_invalid_suggest_count():
    """잘못된 suggestCount로 채팅 요청 시 에러 테스트"""
    request_data = {
        "userQuestion": "연쇄법칙이 뭐야?",
        "major": "수학",
        "subField": "미적분학",
        "followupMode": "never",
        "suggestCount": 3  # 잘못된 값
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 400
    assert "suggestCount must be 0" in response.json()["detail"]

def test_suggestions_endpoint():
    """제안 엔드포인트 테스트"""
    request_data = {
        "conversationId": "test-uuid-123",
        "major": "수학",
        "subField": "미적분학",
        "suggestCount": 3
    }
    
    response = client.post("/suggestions", json=request_data)
    
    # 응답 구조 검증
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) <= 3  # 요청한 개수 이하

def test_suggestions_endpoint_different_count():
    """다른 제안 개수로 테스트"""
    request_data = {
        "conversationId": "test-uuid-456",
        "major": "물리학",
        "subField": "역학",
        "suggestCount": 5
    }
    
    response = client.post("/suggestions", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) <= 5

def test_chat_stream_endpoint():
    """스트리밍 채팅 엔드포인트 테스트"""
    response = client.get("/chat/stream?question=미분이란?&major=수학&sub_field=미적분학")
    
    assert response.status_code == 200
    # charset=utf-8이 포함될 수 있으므로 text/plain으로 시작하는지 확인
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["connection"] == "keep-alive"

def test_missing_required_fields():
    """필수 필드 누락 시 에러 테스트"""
    # userQuestion 누락
    request_data = {
        "major": "수학",
        "subField": "미적분학",
        "followupMode": "never",
        "suggestCount": 0
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 422  # Validation error
    
    # major 누락
    request_data = {
        "userQuestion": "연쇄법칙이 뭐야?",
        "subField": "미적분학",
        "followupMode": "never",
        "suggestCount": 0
    }
    
    response = client.post("/chat", json=request_data)
    assert response.status_code == 422

def test_client_request_id_header():
    """클라이언트 요청 ID 헤더 처리 테스트"""
    request_data = {
        "userQuestion": "테스트 질문",
        "major": "테스트",
        "subField": "테스트",
        "followupMode": "never",
        "suggestCount": 0
    }
    
    # 클라이언트 요청 ID 포함
    response = client.post("/chat", json=request_data, headers={"x-client-request-id": "test-id-123"})
    assert response.status_code == 200
    assert response.headers["x-client-request-id"] == "test-id-123"
    
    # 클라이언트 요청 ID 없음 (자동 생성)
    response = client.post("/chat", json=request_data)
    assert response.status_code == 200
    assert "x-client-request-id" in response.headers

def test_echo_endpoint():
    """기존 echo 엔드포인트 테스트"""
    response = client.get("/api/v1/echo?q=test")
    assert response.status_code == 200
    assert response.json() == {"echo": "test"}
    
    # 기본값 테스트
    response = client.get("/api/v1/echo")
    assert response.status_code == 200
    assert response.json() == {"echo": "hello"}


