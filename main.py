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
    logger.info("Initializing HelpDesk AI Backend...")
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.critical("FATAL: Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables.")
        raise RuntimeError("Missing required Supabase environment configuration.")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Successfully established connection to Supabase PostgreSQL.")
    except Exception as e:
        logger.critical(f"Failed to connect to Supabase: {e}")
        raise e
    yield

app = FastAPI(title="HelpDesk AI Enterprise API", version="2.0.0", lifespan=lifespan)

allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=2)
    description: str = Field(..., min_length=3)
    category: Optional[str] = "general"
    priority: Optional[str] = "medium"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None

@app.get("/healthz", tags=["System"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

# --- PERSISTENT SUPABASE CRUD ENDPOINTS ---

@app.get("/api/tickets", tags=["Tickets"])
def get_tickets():
    """Fetch persistent ticket records from Supabase PostgreSQL."""
    try:
        res = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Failed to query tickets from Supabase: {e}")
        raise HTTPException(status_code=500, detail="Database fetch error")

@app.post("/api/tickets", status_code=201, tags=["Tickets"])
def create_ticket(ticket: TicketCreate):
    """Insert persistent ticket record into Supabase PostgreSQL."""
    try:
        payload = {
            "title": ticket.title.strip(),
            "description": ticket.description.strip(),
            "category": ticket.category,
            "priority": ticket.priority,
            "status": "open",
            "assignee_name": "Unassigned"
        }
        res = supabase.table("tickets").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Database insert returned empty result")
        logger.info(f"Successfully created ticket {res.data[0].get('id')} in Supabase.")
        return res.data[0]
    except Exception as e:
        logger.error(f"Supabase persistence failure: {e}")
        raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")

@app.patch("/api/tickets/{ticket_id}", tags=["Tickets"])
def update_ticket(ticket_id: str, updates: TicketUpdate):
    """Update persistent ticket record in Supabase PostgreSQL."""
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        res = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        return res.data[0] if res.data else {"status": "updated"}
    except Exception as e:
        logger.error(f"Failed to patch ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Database update failed")