# AWS Lambda Deployment (FastAPI + Mangum)

This guide describes how to deploy the FastAPI app to AWS Lambda using Mangum.

## Prerequisites
- Python 3.10+
- AWS account access with permission to create Lambda functions
- Region: `us-east-1`

## Local Test
- Run locally with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Expected responses:
  - `GET http://localhost:8000/health` → `{ "status": "ok" }`
  - `GET http://localhost:8000/api/v1/echo?q=hello` → `{ "echo": "hello" }`

## Build Lambda Package
- One-shot build (no venv dependency):
```bash
chmod +x scripts/build_lambda.sh
./scripts/build_lambda.sh
```
- Output: `lambda.zip` containing dependencies and `app/` code.

## Create Lambda (Console)
1. Go to AWS Console → Lambda → Create function
2. Author from scratch
   - Name: `kus-aws-backend`
   - Runtime: `Python 3.10`
   - Architecture: `x86_64`
   - Permissions → Choose existing role: `SafeRoleForUser-{username}`
   - Create function
3. Upload code
   - Upload from → `.zip file` → select `lambda.zip`
4. Set handler
   - Handler: `app.main.handler`
5. Basic settings
   - Memory/Timeout as needed (e.g., 512 MB, 15 sec)
6. Save and Deploy

## API Gateway (HTTP API)
1. Add trigger → API Gateway → Create an API → HTTP API (not REST)
2. Security: `Open` (demo) or configure auth as needed
3. CORS: Enable with defaults (demo). Consider restricting allowed origins for production.

## Notes
- The FastAPI app is wrapped by Mangum: `handler = Mangum(app)`
- CORS is currently permissive (`*`) for demo only; restrict in production.
- Do not embed secrets in code; use environment variables or AWS Parameter Store/Secrets Manager.
