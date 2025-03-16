from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from groq import Groq
import uuid
from pydantic import BaseModel
from modules.devfeedback import DeveloperFeedback
from modules.autocomplete import generate_code_completion
from modules.autocomment import generate_code_comments
import asyncio
import logging
from dotenv import load_dotenv
import os

load_dotenv()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Developer Assistant API with Feedback")

# CORS configuration (combining both sets of origins)
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "*"  # Adjust this in production to specific domains
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase setup (from devfeedback.py)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Groq setup (from devfeedback.py)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize DeveloperFeedback
dev_feedback = DeveloperFeedback(supabase, groq_client)

# Pydantic models
class CodeEvent(BaseModel):
    session_id: str
    code: str
    chars_typed: int
    chars_deleted: int
    errors: int

class CodeCompletionRequest(BaseModel):
    code: str
    language: str
    cursor_position: int
    file_name: str = ""  # Optional

class CodeCommentRequest(BaseModel):
    code: str
    language: str
    file_name: str = ""  # Optional

# Developer Feedback Endpoints (from devfeedback.py)
@app.get("/start-session/{username}")
async def start_session(username: str):
    user = supabase.table("users").select("user_id").eq("username", username).execute().data
    if not user:
        user_id = str(uuid.uuid4())
        supabase.table("users").insert({"user_id": user_id, "username": username}).execute()
    else:
        user_id = user[0]["user_id"]

    session_id = str(uuid.uuid4())
    data = {"session_id": session_id, "user_id": user_id}
    supabase.table("coding_sessions").insert(data).execute()
    logger.info(f"Session started: {session_id}")
    return {"session_id": session_id}

@app.post("/log-code-event")
async def log_code_event(event: CodeEvent):
    logger.info(f"Logging event for session {event.session_id}: code={event.code[:50]}..., chars_typed={event.chars_typed}, errors={event.errors}")
    await dev_feedback.log_code_event(
        event.session_id, event.code, event.chars_typed, event.chars_deleted, event.errors
    )
    return {"status": "logged"}

@app.get("/get-feedback/{session_id}")
async def get_feedback(session_id: str):
    logger.info(f"Generating feedback for session {session_id}")
    feedback = await dev_feedback.generate_final_feedback(session_id)
    logger.info(f"Feedback response sent to frontend: {feedback}")
    return {"feedback": feedback}

# AI Developer Assistant Endpoints (from main project)
@app.post("/api/autocomplete")
async def autocomplete(request: CodeCompletionRequest):
    try:
        completion_results = await generate_code_completion(
            code=request.code,
            language=request.language,
            cursor_position=request.cursor_position,
            file_name=request.file_name
        )
        return {"suggestions": completion_results}
    except Exception as e:
        logger.error(f"Error in autocomplete endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/autocomment")
async def autocomment(request: CodeCommentRequest):
    try:
        comment_results = await generate_code_comments(
            code=request.code,
            language=request.language,
            file_name=request.file_name
        )
        return comment_results
    except Exception as e:
        logger.error(f"Error in autocomment endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)