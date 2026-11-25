from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import get_settings
from . import auth

app = FastAPI(title="TechDocs AI")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)

@app.get("/health")
def health():
    return {"status": "ok"}
