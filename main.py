import os
import jwt
import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title="HelpDesk AI Enterprise API", version="2.0")

# CORS Setup
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "6c53874c-0e58-4061-9c91-69cd9a8ceef0")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class TicketCreate(BaseModel):
    title: str
    description: str
    category: Optional[str] = "general"
    priority: Optional[str] = "medium"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None

# --- AUTHENTICATION & PERMISSIONS DEPENDENCIES ---

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Verifies Bearer JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

def require_agent_role(user: dict = Depends(get_current_user)) -> dict:
    """Role Guard: Restricts endpoint access to Agents and Admins only."""
    user_role = user.get("role", "employee").lower()
    if user_role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role: 'agent' or 'admin'. Your role: '{user_role}'."
        )
    return user

# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"status": "ok", "service": "HelpDesk AI API", "version": "2.0"}

@app.post("/api/login")
def login(creds: LoginRequest):
    """Generates signed JWT tokens with assigned user roles."""
    # Demo User Accounts
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
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data
    }

@app.get("/api/tickets")
def get_tickets():
    try:
        res = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/tickets", status_code=201)
def create_ticket(ticket: TicketCreate):
    if not ticket.title.strip() or not ticket.description.strip():
        raise HTTPException(status_code=422, detail="Title and description cannot be empty")
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
        raise HTTPException(status_code=500, detail=f"Ticket creation failed: {str(e)}")

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str, 
    updates: TicketUpdate, 
    agent: dict = Depends(require_agent_role)  # Protected by Role Guard
):
    """Requires active 'agent' or 'admin' Bearer JWT token."""
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid update fields provided")
    try:
        res = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        return res.data[0] if res.data else {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ticket: {str(e)}")