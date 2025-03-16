import os
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get API key from environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Make sure to set this environment variable or update it here
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in environment variables")

async def generate_code_completion(
    code: str, 
    language: str, 
    cursor_position: int,
    file_name: str = ""
) -> List[Dict[str, Any]]:
    """
    Generate code completion suggestions based on the current code and cursor position.
    
    Args:
        code: The current code content
        language: Programming language (e.g., "python", "javascript")
        cursor_position: Current cursor position in the code
        file_name: Optional file name for additional context
    
    Returns:
        A list of completion suggestions with text and additional info
    """
    # Extract the context before cursor for better completions
    context = code[:cursor_position]
    
    # Create prompt for the LLM
    prompt = f"""You are an expert {language} programmer. Complete the following code snippet.
    Focus only on providing useful code completions, not explanations.
    
    File: {file_name if file_name else "Untitled"}
    Language: {language}
    
    Code context up to cursor:
    ```{language}
    {context}
    ```
    
    Provide up to 3 different completion suggestions. Format your response as a JSON list with each suggestion containing:
    - "text": The suggested completion text
    - "description": A very brief description of what this completion does
    - "kind": One of "function", "variable", "class", "keyword", "property", "method", "snippet", or "other"
    
    Return only JSON array, no explanations or other text.
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "You are an AI code assistant that provides concise and accurate code completions."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 300
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Error from Groq API: {response.text}")
                return [{"text": "Error fetching suggestions", "description": "API error", "kind": "other"}]
            
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
            
            # Parse the JSON response
            import json
            try:
                # The LLM might return markdown-formatted JSON, so we need to clean it
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                suggestions = json.loads(content)
                
                # Validate and clean suggestions
                validated_suggestions = []
                for suggestion in suggestions:
                    if isinstance(suggestion, dict) and "text" in suggestion:
                        validated_suggestions.append({
                            "text": suggestion.get("text", ""),
                            "description": suggestion.get("description", ""),
                            "kind": suggestion.get("kind", "other")
                        })
                
                return validated_suggestions
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from LLM response: {e}")
                # If JSON parsing fails, try to extract something useful
                return [{"text": content[:50] + "...", "description": "Parsed from response", "kind": "snippet"}]
                
    except Exception as e:
        logger.error(f"Error in generate_code_completion: {str(e)}")
        return [{"text": "Error generating completion", "description": str(e), "kind": "other"}]

# Utility function to determine code language from file extension
def get_language_from_filename(filename: str) -> str:
    """Determine programming language based on file extension"""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".php": "php",
        ".rb": "ruby",
        ".rs": "rust",
        ".sh": "bash",
    }
    
    ext = os.path.splitext(filename)[1].lower()
    return ext_map.get(ext, "plaintext")