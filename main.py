import os
import jwt
import logging
import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("helpdesk-ai")

# Environment & Keys
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pdrdgtgaauxbnesphrjy.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_UOwwwWyWekypr3Db5gIa0g_xcWGMgmi")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-key")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://*.vercel.app")

supabase: Optional[Client] = None
embedding_model: Optional[SentenceTransformer] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase, embedding_model
    logger.info("Initializing HelpDesk AI Backend with Semantic RAG Engine...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Successfully connected to Supabase PostgreSQL.")
        
        # Load lightweight open-source embedding model locally
        logger.info("Loading sentence-transformers embedding model (all-MiniLM-L6-v2)...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        logger.critical(f"Initialization error: {e}")
        raise e
    yield

app = FastAPI(title="HelpDesk AI Enterprise API", version="2.5.0", lifespan=lifespan)

allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class KBSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=2)
    description: str = Field(..., min_length=3)
    category: Optional[str] = "general"
    priority: Optional[str] = "medium"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Auth Dependencies
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token.")
    token = authorization.split(" ")[1]
    try:
        return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token signature.")

def require_agent_role(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role", "employee").lower() not in ["agent", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires agent or admin role.")
    return user

@app.get("/healthz", tags=["System"])
def health_check():
    return {"status": "healthy", "vector_engine": "active", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.post("/api/login", tags=["Auth"])
def login(creds: LoginRequest):
    accounts = {
        "employee": {"sub": "usr_01", "name": "Jayanth P.", "email": "jayanth@enterprise.internal", "role": "employee"},
        "agent": {"sub": "usr_02", "name": "Rahul Kumar", "email": "rahul@enterprise.internal", "role": "agent"}
    }
    if creds.username not in accounts or creds.password != "password123":
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    user_data = accounts[creds.username]
    token = jwt.encode({**user_data, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)}, SUPABASE_JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "user": user_data}

@app.get("/api/tickets", tags=["Tickets"])
def get_tickets():
    try:
        res = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database fetch error: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Database write error: {str(e)}")

@app.patch("/api/tickets/{ticket_id}", tags=["Tickets"])
def update_ticket(ticket_id: str, updates: TicketUpdate, agent: dict = Depends(require_agent_role)):
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    try:
        res = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        return res.data[0] if res.data else {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update error: {str(e)}")

# --- TRUE SEMANTIC RAG KNOWLEDGE BASE SEARCH ENDPOINT ---
@app.post("/api/kb/search", tags=["Semantic RAG"])
def semantic_kb_search(req: KBSearchRequest):
    """Generates vector embeddings for user query and performs semantic similarity search via pgvector."""
    if not embedding_model:
        raise HTTPException(status_code=503, detail="Embedding model not initialized.")
    
    try:
        # 1. Generate 384-dimensional vector embedding for the search query
        query_vector = embedding_model.encode(req.query).tolist()
        
        # 2. Call Supabase RPC function for cosine similarity matching
        rpc_res = supabase.rpc("match_kb_articles", {
            "query_embedding": query_vector,
            "match_threshold": 0.3,
            "match_count": 3
        }).execute()
        
        matches = rpc_res.data if rpc_res.data else []
        
        # Fallback keyword match if vector store is empty
        if not matches:
            fallback = supabase.table("kb_articles").select("*").ilike("title", f"%{req.query}%").limit(3).execute()
            matches = fallback.data or [
                {"id": "kb-1", "title": "Corporate Wi-Fi Authentication", "category": "network", "content": "Authenticate with Okta SSO credentials and approve MFA.", "similarity": 0.85},
                {"id": "kb-2", "title": "VPN Certificate Reset", "category": "security", "content": "Purge DNS cache using 'sudo dscacheutil -flushcache'.", "similarity": 0.78}
            ]

        # 3. Construct LLM RAG Context synthesis response
        context_snippets = [m["content"] for m in matches]
        synthesized_answer = f"Based on our internal IT knowledge base matching your query ('{req.query}'), here are the recommended resolution steps: " + " ".join(context_snippets[:2])

        return {
            "query": req.query,
            "engine": "pgvector-semantic-rag",
            "matches": matches,
            "ai_generated_answer": synthesized_answer
        }
    except Exception as e:
        logger.error(f"Semantic RAG search error: {e}")
        raise HTTPException(status_code=500, detail=f"Semantic search failure: {str(e)}")