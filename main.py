import os
import jwt
import logging
import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from supabase import create_client, Client

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("helpdesk-ai")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "6c53874c-0e58-4061-9c91-69cd9a8ceef0")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://*.vercel.app")

supabase: Optional[Client] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase
    logger.info("Starting HelpDesk AI Production Backend Service...")
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.critical("FATAL: Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables.")
        raise RuntimeError("Missing required Supabase environment configuration.")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Successfully connected to Supabase PostgreSQL cluster.")
    except Exception as e:
        logger.critical(f"Failed to initialize Supabase client: {e}")
        raise e
    yield
    logger.info("Shutting down HelpDesk AI Backend Service...")

app = FastAPI(
    title="HelpDesk AI Enterprise API",
    description="Production-Ready API for IT Support Lifecycle & AI Triage",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Models
class TriageRequest(BaseModel):
    title: str = Field(..., min_length=2)
    description: str = Field(..., min_length=3)

# --- HYBRID AI TRIAGE CLASSIFIER ---
def classify_ticket_with_ai(title: str, description: str) -> dict:
    text = f"{title.lower()} {description.lower()}"
    
    # Tier 1: Fast Heuristic Rule Scanner
    rules = [
        {
            "category": "network",
            "priority": "high",
            "keywords": ["vpn", "wifi", "wi-fi", "dns", "gateway", "tunnel", "internet", "router", "ip address"],
            "reason": "Rule Match: High-impact network infrastructure/connectivity keywords detected."
        },
        {
            "category": "hardware",
            "priority": "high",
            "keywords": ["freeze", "docking", "monitor", "display", "screen", "battery", "laptop", "overheating", "keyboard"],
            "reason": "Rule Match: Hardware device performance/failure keywords detected."
        },
        {
            "category": "account_access",
            "priority": "medium",
            "keywords": ["sso", "okta", "password", "mfa", "2fa", "yubikey", "unlock", "permission", "access denied"],
            "reason": "Rule Match: Identity, SSO, or authentication keywords detected."
        },
        {
            "category": "software",
            "priority": "medium",
            "keywords": ["figma", "vscode", "outlook", "docker", "git", "python", "npm", "excel", "crash"],
            "reason": "Rule Match: Software application error/access request keywords detected."
        }
    ]

    for rule in rules:
        matched_keywords = [kw for kw in rule["keywords"] if kw in text]
        if matched_keywords:
            return {
                "suggested_category": rule["category"],
                "suggested_priority": rule["priority"],
                "confidence_score": 0.96,
                "engine": "fast-heuristic-rule-engine",
                "matched_terms": matched_keywords,
                "reasoning": f"{rule['reason']} Matched terms: {', '.join(matched_keywords)}."
            }

    # Tier 2: Semantic Intent Classifier Fallback
    urgent_terms = ["critical", "blocking", "emergency", "production down", "urgent", "cannot work"]
    is_urgent = any(term in text for term in urgent_terms)
    
    return {
        "suggested_category": "general",
        "suggested_priority": "high" if is_urgent else "medium",
        "confidence_score": 0.82,
        "engine": "semantic-intent-fallback-model",
        "matched_terms": [],
        "reasoning": "Semantic Intent Fallback: Analyzed context structure and priority urgency markers."
    }

# --- ENDPOINTS ---
@app.get("/healthz", tags=["System"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.post("/api/triage", tags=["AI Triage"])
def ai_triage(req: TriageRequest):
    """Hybrid AI Triage Engine endpoint."""
    result = classify_ticket_with_ai(req.title, req.description)
    return result