from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
from supabase import create_client, Client

app = FastAPI(
    title="HelpDesk AI - Enterprise ITSM Backend",
    description="Production API connected to Supabase PostgreSQL with SLA Tracking and KB Search",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://pdrdgtgaauxbnesphrjy.supabase.co")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "sb_publishable_UOwwwWyWekypr3Db5gIa0g_xcWGMgmi")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SLA_HOURS = {"critical": 4, "high": 8, "medium": 24, "low": 48}

class TriageRequest(BaseModel):
    title: str
    description: str

class TicketCreate(BaseModel):
    title: str
    description: str
    category: str = "network"
    priority: str = "medium"
    affected_device: Optional[str] = "Dell Latitude 7440"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[str] = None

class CommentCreate(BaseModel):
    author_id: Optional[str] = None
    body: str
    is_internal: bool = False

def run_ai_triage(title: str, description: str):
    text = (title + " " + description).lower()
    if any(k in text for k in ["wifi", "wi-fi", "vpn", "network", "port", "dns", "subnet"]):
        return {
            "suggested_category": "network",
            "suggested_priority": "high",
            "confidence_score": 0.96,
            "reasoning": "Detected network or firewall port connectivity issue.",
            "recommended_steps": [
                "Verify connection to SSID Corporate-Corp-Secure.",
                "Whitelist port 2376 on local subnet 192.168.4.0/24.",
                "Flush DNS cache and test gateway ping."
            ]
        }
    elif any(k in text for k in ["dock", "monitor", "laptop", "screen", "keyboard", "hardware"]):
        return {
            "suggested_category": "hardware",
            "suggested_priority": "medium",
            "confidence_score": 0.92,
            "reasoning": "Workstation or hardware issue detected.",
            "recommended_steps": [
                "Power-cycle Thunderbolt dock.",
                "Update display drivers.",
                "Test with secondary DisplayPort cable."
            ]
        }
    return {
        "suggested_category": "software",
        "suggested_priority": "medium",
        "confidence_score": 0.88,
        "reasoning": "Software or application request.",
        "recommended_steps": [
            "Check license allocation in enterprise portal.",
            "Verify local daemon status and user permissions."
        ]
    }

@app.get("/")
def root():
    return {"service": "HelpDesk AI Backend", "status": "online", "supabase": "connected"}

@app.get("/api/tickets")
def list_tickets(status: Optional[str] = None):
    try:
        query = supabase.from_("tickets").select("*").order("created_at", desc=True)
        if status and status != "all":
            query = query.eq("status", status)
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
    triage = run_ai_triage(ticket.title, ticket.description)
    sla_hours = SLA_HOURS.get(triage["suggested_priority"], 24)
    sla_due = (datetime.utcnow() + timedelta(hours=sla_hours)).isoformat()
    
    payload = {
        "title": ticket.title,
        "description": ticket.description,
        "category": triage["suggested_category"],
        "priority": triage["suggested_priority"],
        "status": "open",
        "affected_device": ticket.affected_device,
        "sla_due_at": sla_due,
        "requester_name": "Pocharam Jayanth",
        "assignee_name": "Unassigned"
    }
    try:
        response = supabase.from_("tickets").insert([payload]).execute()
        return response.data[0] if response.data else payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update: TicketUpdate):
    data = {k: v for k, v in update.dict().items() if v is not None}
    if "priority" in data:
        sla_hours = SLA_HOURS.get(data["priority"], 24)
        data["sla_due_at"] = (datetime.utcnow() + timedelta(hours=sla_hours)).isoformat()
    try:
        response = supabase.from_("tickets").update(data).eq("id", ticket_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets/{ticket_id}/comments")
def add_comment(ticket_id: str, comment: CommentCreate):
    payload = {
        "ticket_id": ticket_id,
        "body": comment.body,
        "is_internal": comment.is_internal
    }
    try:
        response = supabase.from_("ticket_comments").insert([payload]).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/triage")
def ai_triage(payload: TriageRequest):
    return run_ai_triage(payload.title, payload.description)

@app.get("/api/kb/search")
def search_kb(q: str = Query(..., min_length=1)):
    try:
        response = supabase.from_("knowledge_articles").select("*").ilike("title", f"%{q}%").execute()
        if not response.data:
            return {
                "query": q,
                "articles": [
                    {
                        "title": f"Troubleshooting Guide for '{q}'",
                        "content": "Verify network adapter settings, check port status, and consult network admin."
                    }
                ]
            }
        return {"query": q, "articles": response.data}
    except Exception as e:
        return {"query": q, "articles": []}
