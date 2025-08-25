from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os
import json
from typing import List
from pydantic import BaseModel

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


class HealthResponse(BaseModel):
    status: str


class EchoResponse(BaseModel):
    echo: str


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    response = await call_next(request)
    log_record = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
    }
    print(json.dumps(log_record, ensure_ascii=False))
    return response

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
