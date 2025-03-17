# modules/autoformat.py
import re
import logging
from typing import Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class CodeFormatter:
    def __init__(self, groq_client):
        self.groq_client = groq_client
        logger.info("CodeFormatter initialized")

    async def format_code(self, code: str, language: str, file_name: str = "") -> Dict[str, Any]:
        """
        Format code according to language-specific standards
        
        Args:
            code: The code to format
            language: Programming language of the code
            file_name: Optional file name for context
            
        Returns:
            Dictionary containing formatted code and metadata
        """
        if not code or len(code.strip()) < 10:
            return {
                "success": False,
                "message": "Code too short for meaningful formatting",
                "formatted_code": code
            }

        # Apply language-specific formatting using LLM
        try:
            language_display = self._get_language_display_name(language, file_name)
            
            # First try to format with built-in rules for faster response
            preliminary_formatted = self._apply_basic_formatting(code, language)
            
            # Then send to LLM for more sophisticated formatting
            prompt = self._create_formatting_prompt(preliminary_formatted, language_display)
            
            logger.info(f"Sending code for formatting ({language_display})")
            
            response = await self._get_llm_formatting(prompt)
            formatted_code = self._extract_code_from_response(response, language)
            
            # Apply consistent indentation as a final step
            formatted_code = self._normalize_indentation(formatted_code, language)
            
            changes_made = code != formatted_code
            
            return {
                "success": True,
                "message": "Code formatted successfully" if changes_made else "No formatting changes needed",
                "formatted_code": formatted_code,
                "changes_made": changes_made
            }
            
        except Exception as e:
            logger.error(f"Error formatting code: {str(e)}")
            return {
                "success": False,
                "message": f"Error formatting code: {str(e)}",
                "formatted_code": code
            }

    def _get_language_display_name(self, language: str, file_name: str) -> str:
        """Get proper display name for the language based on language code and filename"""
        language_map = {
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "python": "Python",
            "java": "Java",
            "csharp": "C#",
            "cpp": "C++",
            "c": "C",
            "go": "Go",
            "rust": "Rust",
            "ruby": "Ruby",
            "php": "PHP",
            "html": "HTML",
            "css": "CSS",
            "json": "JSON",
            "markdown": "Markdown"
        }
        
        # First try language parameter
        if language in language_map:
            return language_map[language]
        
        # If not found, try to infer from file extension
        if file_name:
            ext = file_name.split('.')[-1].lower()
            extension_map = {
                "js": "JavaScript",
                "ts": "TypeScript",
                "py": "Python",
                "java": "Java",
                "cs": "C#",
                "cpp": "C++",
                "c": "C",
                "go": "Go",
                "rs": "Rust",
                "rb": "Ruby",
                "php": "PHP",
                "html": "HTML",
                "htm": "HTML",
                "css": "CSS",
                "json": "JSON",
                "md": "Markdown"
            }
            if ext in extension_map:
                return extension_map[ext]
        
        # Default to original language if we can't determine
        return language.capitalize()

    def _apply_basic_formatting(self, code: str, language: str) -> str:
        """Apply basic formatting rules without calling LLM"""
        # JavaScript/TypeScript basic formatting
        if language in ["javascript", "typescript"]:
            # Add semicolons where missing at end of lines
            code = re.sub(r'}\n', '};\n', code)  # Add semicolons after closing braces
            code = re.sub(r'(\w|\)|\]|\'|\")\s*\n', r'\1;\n', code)  # Add semicolons at end of statements
            
            # Fix spacing around operators
            code = re.sub(r'(\w)\=(\w)', r'\1 = \2', code)  # Add spaces around =
            code = re.sub(r'(\w)(\+|\-|\*|\/|\%)(\w)', r'\1 \2 \3', code)  # Add spaces around operators
            
        # Python basic formatting
        elif language == "python":
            # Ensure two blank lines between top-level functions and classes
            code = re.sub(r'(\n\s*def\s+\w+\([^\)]*\):.*?)(\n\s*def\s+)', r'\1\n\n\2', code, flags=re.DOTALL)
            code = re.sub(r'(\n\s*class\s+\w+.*?)(\n\s*def\s+)', r'\1\n\n\2', code, flags=re.DOTALL)
            
            # Fix indentation (assume 4 spaces)
            lines = code.split('\n')
            for i in range(len(lines)):
                # Replace tabs with spaces
                if '\t' in lines[i]:
                    lines[i] = lines[i].replace('\t', '    ')
            
            code = '\n'.join(lines)
            
        # HTML basic formatting
        elif language == "html":
            # Add proper line breaks after tags
            code = re.sub(r'>\s*<', '>\n<', code)
            
        return code

    def _create_formatting_prompt(self, code: str, language: str) -> str:
        """Create a prompt for the LLM to format the code"""
        return f"""Format the following {language} code according to best practices for that language. 
Apply consistent indentation, spacing, and line breaks.
Fix any obvious formatting issues.
Only return the properly formatted code without explanations.

CODE TO FORMAT:
```{language.lower()}
{code}
```
FORMATTED CODE:"""

    async def _get_llm_formatting(self, prompt: str) -> str:
        """Send code to LLM for formatting"""
        try:
            # Create a chat completion using Groq
            response = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": "You are a code formatting assistant. You only return formatted code without explanations or comments."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent formatting
                max_tokens=8000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error from LLM formatting API: {str(e)}")
            raise

    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Extract the formatted code from the LLM response"""
        # Try to extract code from markdown code blocks
        code_block_pattern = f"```(?:{language}|{language.lower()}|{language.upper()})?\n(.*?)```"
        matches = re.search(code_block_pattern, response, re.DOTALL)
        
        if matches:
            return matches.group(1).strip()
        
        # If no code block found, return the whole response
        return response.strip()

    def _normalize_indentation(self, code: str, language: str) -> str:
        """Normalize indentation based on language"""
        lines = code.split('\n')
        result_lines = []
        
        # Determine the indentation character and size based on language
        if language == "python":
            indent_char = " "
            indent_size = 4
        else:  # Default for most other languages
            indent_char = " "
            indent_size = 2
        
        current_indent = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                result_lines.append("")
                continue
                
            # Adjust indentation based on braces/brackets for C-style languages
            if language in ["javascript", "typescript", "java", "c", "cpp", "csharp"]:
                # Decrease indent if line starts with closing brace
                if stripped.startswith('}') or stripped.startswith(')') or stripped.startswith(']'):
                    current_indent = max(0, current_indent - 1)
                
                # Add line with current indentation
                result_lines.append(indent_char * (indent_size * current_indent) + stripped)
                
                # Increase indent if line ends with opening brace
                if stripped.endswith('{') or stripped.endswith('(') or stripped.endswith('['):
                    current_indent += 1
            else:
                # For Python, we keep the indentation as is (already normalized in previous steps)
                result_lines.append(line)
                
        return '\n'.join(result_lines)

# Helper function for module usage from app.py
async def format_code(code, language, file_name="", groq_client=None):
    """Format code using the CodeFormatter class"""
    formatter = CodeFormatter(groq_client)
    result = await formatter.format_code(code, language, file_name)
    return result