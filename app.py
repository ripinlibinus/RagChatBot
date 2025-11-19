# app.py
import os
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
import time
import logging
from pydantic import BaseModel

from api_rval import build_chain as build_chain_api
from vector_rval import build_chain as build_chain_vector
from api_vector_rval import build_chain as build_chain_hybrid



app = FastAPI(title="Real Estate RAG ChatBot", version="1.0.0")

class MessageInbound(BaseModel):
    sender_id: str           
    sender_name: str
    question: str 
    method: str | None = None     

    # optional metadata kalau kamu kirim dari Node
    ts: str | None = None
    msg_id: str | None = None

    # izinkan input pakai nama field asli (sender/message) maupun alias (from/text)
    model_config = ConfigDict(populate_by_name=True)

logger = logging.getLogger("app.timing")

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    logger.info("%s %s %s %0.1fms",
                request.method, request.url.path, response.status_code, ms)
    return response

@app.get("/health")
def health():
    return {"status": "Chatbot Ready"}

@app.post("/question_hook")
def question_hook(payload: MessageInbound):

    # Pilih fungsi build_chain sesuai argumen
    if payload.method == "api":
        build_chain = build_chain_api
    elif payload.method == "vector":
        build_chain = build_chain_vector
    else:
        build_chain = build_chain_hybrid
    
    try:
        reply = build_chain({
            "question" : payload.question, 
            "session_id" : payload.sender_id,
            "user_name" : payload.sender_name,
        })   
    except Exception as e:
        # Jangan bocorkan error lengkap ke user
        raise HTTPException(status_code=500, detail=f"RAG error: {type(e).__name__}: {e}") from e

    response = {
        "code": 200,
        "status": "ok",
        "method" : payload.method if payload.method else "hybrid",
        "answer": reply
    }

    return response
