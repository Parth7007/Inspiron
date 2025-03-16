import os
import asyncio
import httpx
import logging
from typing import Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get API key from environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def generate_code_comments(
    code: str,
    language: str,
    file_name: str = ""
) -> Dict[str, Any]:
    """
    Generate appropriate comments for the given code.
    
    Args:
        code: The current code content
        language: Programming language (e.g., "python", "javascript")
        file_name: Optional file name for additional context
    
    Returns:
        Dictionary containing the commented code and metadata
    """
    # Skip if code is too short or empty
    if len(code.strip()) < 10:
        return {
            "commented_code": code,
            "success": False,
            "message": "Code too short for meaningful comments"
        }
    
    try:
        prompt = f"""You are an expert {language} programmer tasked with adding helpful comments to code.
        Analyze the following code and add appropriate comments that explain:
        1. The purpose of functions, classes, and methods
        2. Complex logic or algorithms
        3. Non-obvious implementation details
        
        Only add comments where they add value. Do not comment obvious code.
        Use the standard comment syntax for {language}.
        
        File: {file_name if file_name else "Untitled"}
        Language: {language}
        
        Code to comment:
        ```{language}
        {code}
        ```
        
        Return ONLY the commented code without any explanations or markdown formatting.
        Preserve ALL original code exactly as is, only adding comments.
        """
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "You are an AI code assistant that adds helpful, concise comments to code without changing the original code."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1500
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Sending request to Groq API for code commenting")
            response = await client.post(
                GROQ_API_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Error from Groq API: {response.text}")
                return {
                    "commented_code": code,
                    "success": False,
                    "message": f"API error: {response.status_code}"
                }
            
            response_data = response.json()
            logger.info(f"Received response from Groq API")
            content = response_data["choices"][0]["message"]["content"]
            
            # Extract code from possible markdown formatting
            if "```" in content:
                # Extract content between the first and last code block markers
                start_marker = "```" + language
                if start_marker in content:
                    start_index = content.find(start_marker) + len(start_marker)
                else:
                    start_index = content.find("```") + 3
                    # Find the language identifier if it exists
                    if content[start_index:].find("\n") > 0:
                        start_index = content.find("\n", start_index) + 1
                end_index = content.rfind("```")
                commented_code = content[start_index:end_index].strip()
            else:
                commented_code = content.strip()
                
            logger.info(f"Successfully generated comments for code")
            return {
                "commented_code": commented_code,
                "success": True,
                "message": "Comments added successfully"
            }
                
    except Exception as e:
        logger.error(f"Error in generate_code_comments: {str(e)}")
        return {
            "commented_code": code,
            "success": False,
            "message": f"Error: {str(e)}"
        }

async def analyze_code_blocks(
    code: str,
    language: str
) -> List[Dict[str, Any]]:
    """
    Analyze code to identify logical blocks that might need comments.
    
    Args:
        code: The code to analyze
        language: The programming language
        
    Returns:
        List of code blocks with positions that might need comments
    """
    # This is a simplified implementation
    # A more sophisticated version would parse the code and identify
    # functions, classes, and complex blocks
    
    lines = code.split('\n')
    blocks = []
    
    # Different patterns to detect based on language
    function_patterns = {
        'python': ['def ', 'class '],
        'javascript': ['function ', 'class ', '=>', 'async '],
        'typescript': ['function ', 'class ', '=>', 'async ', 'interface '],
        'java': ['public ', 'private ', 'protected ', 'class ', 'void ', 'int ', 'String '],
    }
    
    patterns = function_patterns.get(language, ['function', 'class'])
    
    current_block = {"start": 0, "end": 0, "code": "", "needs_comment": False}
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip empty lines and existing comments
        if not stripped or is_comment_line(stripped, language):
            continue
            
        # Check if this line starts a new block
        is_new_block = False
        for pattern in patterns:
            if pattern in stripped and not is_inside_string(stripped, pattern):
                # This might be a function or class definition
                if current_block["code"]:
                    current_block["end"] = i - 1
                    blocks.append(current_block)
                
                current_block = {
                    "start": i,
                    "end": i,
                    "code": stripped,
                    "needs_comment": True
                }
                is_new_block = True
                break
        
        if not is_new_block and current_block["code"]:
            current_block["code"] += "\n" + stripped
            current_block["end"] = i
    
    # Add the last block
    if current_block["code"] and current_block not in blocks:
        blocks.append(current_block)
    
    return blocks

def is_comment_line(line: str, language: str) -> bool:
    """Check if a line is a comment based on the language"""
    comment_markers = {
        'python': ['#'],
        'javascript': ['//', '/*'],
        'typescript': ['//', '/*'],
        'java': ['//', '/*'],
        'html': ['<!--'],
        'css': ['/*'],
    }
    
    markers = comment_markers.get(language, ['#', '//'])
    
    for marker in markers:
        if line.strip().startswith(marker):
            return True
    
    return False

def is_inside_string(line: str, substring: str) -> bool:
    """Simplified check if a substring appears inside a string literal"""
    # This is a basic implementation - a proper one would use a parser
    quote_positions = []
    for i, char in enumerate(line):
        if char in ['"', "'"]:
            quote_positions.append(i)
    
    if not quote_positions or len(quote_positions) % 2 != 0:
        return False
        
    substring_pos = line.find(substring)
    if substring_pos == -1:
        return False
        
    # Check if substring position is between any pair of quotes
    for i in range(0, len(quote_positions), 2):
        if i + 1 < len(quote_positions):
            if quote_positions[i] < substring_pos < quote_positions[i + 1]:
                return True
                
    return False