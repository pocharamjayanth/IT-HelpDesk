import os
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from supabase import create_client, Client

app = FastAPI(
    title="HelpDesk AI - Enterprise ITSM Backend",
    description="Production API connected to Supabase PostgreSQL with SLA Tracking and KB Search",
    version="2.5.0"
)

# 1. Restrict CORS to trusted local/production origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Require environment variables for Supabase keys (no hardcoded fallbacks)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Data Schemas
class TicketCreate(BaseModel):
    title: str
    description: str
    category: Optional[str] = "network"
    priority: Optional[str] = "medium"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None

class CommentCreate(BaseModel):
    body: str
    is_internal: Optional[bool] = False

class TriageRequest(BaseModel):
    title: str
    description: str

@app.get("/")
def health_check():
    return {"status": "healthy", "version": "2.5.0", "database": "Supabase PostgreSQL"}

@app.get("/api/tickets")
def get_tickets():
    try:
        res = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
    try:
        due_at = (datetime.utcnow() + timedelta(hours=4 if ticket.priority == "critical" else 24)).isoformat()
        new_ticket = {
            "title": ticket.title,
            "description": ticket.description,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": "open",
            "sla_due_at": due_at,
            "requester_name": "Pocharam Jayanth",
            "assignee_name": "Unassigned"
        }
        res = supabase.table("tickets").insert(new_ticket).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, updates: TicketUpdate):
    try:
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        res = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        return res.data[0] if res.data else {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets/{ticket_id}/comments")
def add_comment(ticket_id: str, comment: CommentCreate):
    try:
        new_comment = {
            "ticket_id": ticket_id,
            "body": comment.body,
            "is_internal": comment.is_internal
        }
        res = supabase.table("ticket_comments").insert(new_comment).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/triage")
def ai_triage(req: TriageRequest):
    text = f"{req.title} {req.description}".lower()
    category = "network" if "vpn" in text or "wifi" in text or "port" in text else "hardware" if "dock" in text or "screen" in text else "software"
    priority = "critical" if "blocked" in text or "failure" in text or "down" in text else "medium"
    return {
        "suggested_category": category,
        "suggested_priority": priority,
        "confidence_score": 0.92,
        "reasoning": f"Matched patterns for enterprise {category} infrastructure."
    }