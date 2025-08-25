from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os

app = FastAPI(title="kus-aws-backend")

# 초기 데모용 CORS: 운영 시 Amplify 도메인(예: https://<amplify-domain>)만 허용하도록 제한 필요
# 운영/스테이징에서는 환경 변수 ALLOWED_ORIGINS를 사용(쉼표 구분, 예: https://a.com,https://b.com)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if allowed_origins_env.strip() == "*" else [
    o.strip() for o in allowed_origins_env.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/echo")
def echo(q: str = "hello"):
    return {"echo": q}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

# AWS Lambda handler via Mangum
handler = Mangum(app)
