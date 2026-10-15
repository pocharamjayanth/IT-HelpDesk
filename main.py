from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import re

app = FastAPI(
    title="HelpDesk AI - Enterprise ITSM Backend",
    description="AI Ticket Triage, SLA Calculation, and Knowledge Base RAG API",
    version="2.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TriageRequest(BaseModel):
    title: str
    description: str

class TicketCreate(BaseModel):
    title: str
    description: str
    category: str = "network"
    priority: str = "medium"
    requester: str = "Pocharam Jayanth"
    affected_device: Optional[str] = "Dell Latitude 7440"

TICKETS_DB: List[Dict[str, Any]] = [
    {
        "id": "6ec0c57c-689b-44c7-8101-aeb5203b52ff",
        "ticket_number": "IT-2026-00001",
        "title": "Cannot connect to internal GitLab CI/CD runner",
        "description": "Corporate Wi-Fi blocking port 2376 on Dell Latitude 7440",
        "category": "network",
        "priority": "high",
        "status": "open",
        "requester": "Pocharam Jayanth",
        "assignee": "Unassigned",
        "affected_device": "Dell Latitude 7440",
        "created_at": datetime.utcnow().isoformat()
    }
]

def run_ai_triage(title: str, description: str):
    text = (title + " " + description).lower()
    if any(k in text for k in ["wifi", "wi-fi", "vpn", "network", "port", "dns", "subnet"]):
        return {
            "suggested_category": "network",
            "suggested_priority": "high",
            "confidence_score": 0.96,
            "reasoning": "Detected network or firewall port connectivity issue impacting engineering workflow.",
            "recommended_steps": [
                "Verify connection to SSID Corporate-Corp-Secure.",
                "Whitelist port 2376 on local subnet 192.168.4.0/24.",
                "Flush DNS cache and test gateway ping."
            ]
        }
    elif any(k in text for k in ["dock", "monitor", "laptop", "screen", "keyboard", "battery", "hardware"]):
        return {
            "suggested_category": "hardware",
            "suggested_priority": "medium",
            "confidence_score": 0.92,
            "reasoning": "Physical workstation or peripheral hardware symptom detected.",
            "recommended_steps": [
                "Power-cycle USB-C Thunderbolt dock for 30 seconds.",
                "Update display drivers to corporate v552+.",
                "Test with secondary DisplayPort cable."
            ]
        }
    return {
        "suggested_category": "software",
        "suggested_priority": "medium",
        "confidence_score": 0.88,
        "reasoning": "Standard software provisioning or application configuration request.",
        "recommended_steps": [
            "Check license allocation in the enterprise portal.",
            "Verify local daemon status and user permissions."
        ]
    }

@app.get("/")
def root():
    return {
        "service": "HelpDesk AI Backend",
        "status": "online",
        "supabase_project": "pdrdgtgaauxbnesphrjy",
        "docs_url": "http://127.0.0.1:8000/docs"
    }

@app.get("/api/tickets")
def list_tickets():
    return TICKETS_DB

@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
    triage = run_ai_triage(ticket.title, ticket.description)
    new_ticket = {
        "id": str(uuid.uuid4()),
        "ticket_number": f"IT-2026-0000{len(TICKETS_DB) + 1}",
        "title": ticket.title,
        "description": ticket.description,
        "category": triage["suggested_category"],
        "priority": triage["suggested_priority"],
        "status": "open",
        "requester": ticket.requester,
        "assignee": "Unassigned",
        "affected_device": ticket.affected_device,
        "ai_triage": triage,
        "created_at": datetime.utcnow().isoformat()
    }
    TICKETS_DB.insert(0, new_ticket)
    return new_ticket

@app.post("/api/triage")
def ai_triage_endpoint(payload: TriageRequest):
    return run_ai_triage(payload.title, payload.description)
