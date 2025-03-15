from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from modules.autocomplete import generate_code_completion
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Developer Assistant API")

# Add CORS middleware to allow requests from your React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeCompletionRequest(BaseModel):
    code: str
    language: str
    cursor_position: int
    file_name: str = ""  # Optional, might help with context

@app.post("/api/autocomplete")
async def autocomplete(request: CodeCompletionRequest):
    try:
        # Get code completion suggestions
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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)