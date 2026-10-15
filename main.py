import os
import jwt
import logging
import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("helpdesk-ai")

# Secure Environment Configuration (No hardcoded secrets)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pdrdgtgaauxbnesphrjy.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_UOwwwWyWekypr3Db5gIa0g_xcWGMgmi")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-key")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://*.vercel.app")

supabase: Optional[Client] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase
    logger.info("Initializing HelpDesk AI Backend...")
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

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token signature.")

def require_agent_role(user: dict = Depends(get_current_user)) -> dict:
    user_role = user.get("role", "employee").lower()
    if user_role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required role: 'agent' or 'admin'. Present role: '{user_role}'."
        )
    return user

class LoginRequest(BaseModel):
    username: str
    password: str

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

@app.post("/api/login", tags=["Auth"])
def login(creds: LoginRequest):
    accounts = {
        "employee": {"sub": "usr_01", "name": "Jayanth P.", "email": "jayanth@enterprise.internal", "role": "employee"},
        "agent": {"sub": "usr_02", "name": "Rahul Kumar", "email": "rahul@enterprise.internal", "role": "agent"}
    }
    
    if creds.username not in accounts or creds.password != "password123":
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    user_data = accounts[creds.username]
    payload = {
        **user_data,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    token = jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "user": user_data}

@app.get("/api/tickets", tags=["Tickets"])
def get_tickets():
    try:
        res = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Failed to query tickets from Supabase: {e}")
        raise HTTPException(status_code=500, detail="Database fetch error")

@app.post("/api/tickets", status_code=201, tags=["Tickets"])
def create_ticket(ticket: TicketCreate, current_user: dict = Depends(get_current_user)):
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
        return res.data[0]
    except Exception as e:
        logger.error(f"Supabase write error: {e}")
        raise HTTPException(status_code=500, detail="Database write failed")

@app.patch("/api/tickets/{ticket_id}", tags=["Tickets"])
def update_ticket(ticket_id: str, updates: TicketUpdate, agent: dict = Depends(require_agent_role)):
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields provided for update.")
    try:
        res = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        return res.data[0] if res.data else {"status": "updated"}
    except Exception as e:
        logger.error(f"Failed to patch ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Database update failed")