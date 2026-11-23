"""
FastAPI Backend Server.
Exposes REST endpoints for the Product Analytics Chatbot:
- POST /api/ask: Process question and return SQL, chart spec, and insight
- GET /api/schema: Returns database tables and columns
- GET /api/suggestions: Returns verified sample questions
- POST /api/feedback: Records user thumbs up/down
- GET /api/health: Health check & DB connectivity
"""

import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from backend.pipeline import AnalyticsPipeline
from backend.sql_validator import ALLOWED_SCHEMA
from backend.logger import update_feedback

app = FastAPI(
    title="Product Analytics Chatbot API",
    description="Natural-language to secure SQL & automated chart generation",
    version="1.0.0"
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = AnalyticsPipeline()

# Pydantic Schemas
class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="Natural language question")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Optional conversation history")

class AskResponse(BaseModel):
    answer_id: str
    session_id: str
    question: str
    insight: str
    sql: Optional[str] = None
    columns: List[str] = []
    rows: List[List[Any]] = []
    chart: Dict[str, Any]
    latency_ms: float
    error: Optional[str] = None

class FeedbackRequest(BaseModel):
    answer_id: str
    feedback: str = Field(..., pattern="^(thumbs_up|thumbs_down)$")
    notes: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    database_file: str
    database_connected: bool

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    db_path = os.getenv("DATABASE_PATH", "data/analytics.duckdb")
    db_exists = os.path.exists(db_path)
    return {
        "status": "healthy",
        "llm_provider": os.getenv("LLM_PROVIDER", "mock"),
        "database_file": db_path,
        "database_connected": db_exists
    }

@app.get("/api/schema")
def get_schema():
    """
    Returns the allow-listed database schema for display in UI sidebars.
    """
    return {
        "tables": {
            table: sorted(list(columns))
            for table, columns in ALLOWED_SCHEMA.items()
        }
    }

@app.get("/api/suggestions")
def get_suggestions():
    """
    Returns suggested click-to-ask example questions for new users.
    """
    return {
        "suggestions": [
            {
                "title": "Weekly Signups",
                "question": "Show weekly signups for the last 3 months",
                "category": "Trend"
            },
            {
                "title": "Top Countries",
                "question": "Top 5 countries by signups last month",
                "category": "Ranking"
            },
            {
                "title": "Checkout Funnel",
                "question": "Where do users drop off in checkout?",
                "category": "Funnel"
            },
            {
                "title": "Device Comparison",
                "question": "Compare mobile vs desktop conversion",
                "category": "Segment"
            },
            {
                "title": "Top Products",
                "question": "Top 10 products by revenue",
                "category": "Ranking"
            },
            {
                "title": "Cart to Purchase",
                "question": "Conversion rate from cart to purchase",
                "category": "Funnel"
            }
        ]
    }

@app.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    """
    Processes a user question, runs guardrails, executes SQL, and returns chart + insight.
    """
    try:
        result = pipeline.process_question(
            question=req.question,
            session_id=req.session_id,
            history=req.history
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline processing failed: {str(e)}"
        )

@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    """
    Records user satisfaction feedback (thumbs up / thumbs down).
    """
    update_feedback(req.answer_id, req.feedback, req.notes)
    return {"status": "success", "message": "Feedback recorded."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

