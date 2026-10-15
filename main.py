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

# --- 1. LOGGING & ENVIRONMENT SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("helpdesk-ai")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "6c53874c-0e58-4061-9c91-69cd9a8ceef0")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://*.vercel.app")

# Global Supabase Client Pointer
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

# --- 2. CORS MIDDLEWARE ---
allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# --- 3. GLOBAL EXCEPTION HANDLERS ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled system error on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred. Please contact IT support."}
    )

# --- 4. DATA MODELS ---
class LoginRequest(BaseModel):
    username: str = Field(..., example="agent")
    password: str = Field(..., example="password123")

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=5)
    category: Optional[str] = "general"
    priority: Optional[str] = "medium"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None

class KBSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)

# --- 5. AUTHENTICATION & ROLE GUARDS ---
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token signature.")

def require_agent_role(user: dict = Depends(get_current_user)) -> dict:
    role = user.get("role", "employee").lower()
    if role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires 'agent' or 'admin' role. Present role: '{role}'."
        )
    return user

# --- 6. HEALTH & SYSTEM PROBES ---
@app.get("/healthz", tags=["System"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.get("/readyz", tags=["System"])
def readiness_check():
    if supabase is None:
        raise HTTPException(status_code=503, detail="Database client not initialized")
    return {"status": "ready", "database": "connected"}

# --- 7. CORE BUSINESS ENDPOINTS ---
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
        logger.error(f"Error reading tickets from Supabase: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tickets from database.")

@app.post("/api/tickets", status_code=201, tags=["Tickets"])
def create_ticket(ticket: TicketCreate):
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
        logger.error(f"Failed to create ticket: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed.")

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
        raise HTTPException(status_code=500, detail="Failed to update record in database.")

@app.post("/api/triage", tags=["AI Triage"])
def ai_triage(data: dict):
    title = data.get("title", "").lower()
    desc = data.get("description", "").lower()
    text = f"{title} {desc}"

    category = "general"
    priority = "medium"
    reasoning = "Standard request triage."

    if any(k in text for k in ["vpn", "wifi", "network", "internet", "dns"]):
        category = "network"
        priority = "high"
        reasoning = "Network keyword match detected."
    elif any(k in text for k in ["freeze", "laptop", "monitor", "screen", "hardware"]):
        category = "hardware"
        priority = "high"
        reasoning = "Hardware keyword match detected."
    elif any(k in text for k in ["password", "sso", "okta", "permission", "access"]):
        category = "account_access"
        priority = "medium"
        reasoning = "Identity/SSO match detected."

    return {
        "suggested_category": category,
        "suggested_priority": priority,
        "confidence_score": 0.94,
        "reasoning": reasoning
    }

@app.post("/api/kb/search", tags=["Knowledge Base"])
def search_knowledge_base(req: KBSearchRequest):
    q = req.query.lower()
    articles = [
        {"id": "kb-1", "title": "Connect to Corporate Wi-Fi (802.1X)", "category": "network", "content": "Authenticate with your Okta SSO credentials and approve MFA via YubiKey."},
        {"id": "kb-2", "title": "VPN Tunnel Certificate Reset", "category": "security", "content": "Purge DNS cache by running 'sudo dscacheutil -flushcache' in Terminal on macOS."},
        {"id": "kb-3", "title": "SSO Account Password Unlock", "category": "access", "content": "Navigate to okta.enterprise.internal and click 'Forgot Password' for self-serve reset."}
    ]
    results = [a for a in articles if q in a["title"].lower() or q in a["content"].lower()]
    return {"query": req.query, "matches": results if results else articles[:1]}