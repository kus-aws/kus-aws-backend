from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os

app = FastAPI(title="kus-aws-backend")

# 초기 데모용 CORS: 운영 시 Amplify 도메인(예: https://<amplify-domain>)만 허용하도록 제한 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
