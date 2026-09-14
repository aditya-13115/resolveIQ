from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Make src/ importable
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Load .env before pipeline init
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from api.pipeline import Pipeline  # noqa: E402

app = FastAPI(title="ResolveIQ API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline: Pipeline | None = None


@app.on_event("startup")
def _startup() -> None:
    global _pipeline
    _pipeline = Pipeline(root=ROOT)
    print(f"[api] pipeline loaded. "
          f"{len(_pipeline.corpus)} corpus docs, "
          f"{len(_pipeline.intent_names)} intents.")


class ClassifyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=10)
    force_escalate: bool = False


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "pipeline_loaded": _pipeline is not None,
    }


@app.get("/taxonomy")
def taxonomy() -> dict:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not loaded")
    return _pipeline.get_taxonomy()


@app.post("/classify")
def classify(req: ClassifyRequest) -> dict:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not loaded")
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is empty")
    try:
        return _pipeline.run(
            message,
            top_k=req.top_k,
            force_escalate=req.force_escalate,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")