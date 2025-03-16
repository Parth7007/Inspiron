# meme.py
import requests
from groq import Groq
import json
import logging
import os
import random

logger = logging.getLogger(__name__)

class MemeGenerator:
    def __init__(self, groq_client: Groq):
        self.groq_client = groq_client
        self.giphy_api_key = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")  # Demo key
        self.giphy_api_base = "https://api.giphy.com/v1/gifs/search"

    async def generate_meme_review(self, code: str):
        try:
            # Step 1: Analyze code with Llama
            prompt = f"""
            Analyze this code and provide a short feedback (1-2 sentences) and a single-word or short phrase situation 
            (e.g., 'bug', 'success', 'messy code', 'error', 'clean code') based on syntax, efficiency, or readability:
            ```{code}```
            Return as JSON: {{ "feedback": "string", "situation": "string" }}
            """
            logger.info("Sending request to Groq API")
            ai_response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            response_content = ai_response.choices[0].message.content
            logger.info(f"Groq response: {response_content}")

            # Step 2: Parse response as JSON
            try:
                result = json.loads(response_content)
                if not isinstance(result, dict) or "feedback" not in result or "situation" not in result:
                    raise ValueError("Invalid JSON structure from Groq")
            except json.JSONDecodeError as e:
                logger.warning(f"Groq response not JSON: {response_content}. Using fallback.")
                result = {"feedback": response_content.strip(), "situation": "error"}

            feedback = result.get("feedback", "No feedback provided")
            situation = result.get("situation", "error")

            # Step 3: Fetch funny GIF from GIPHY with randomization
            query = f"funny {situation} programming coding"  # More specific query
            offset = random.randint(0, 50)  # Random offset for variety
            params = {
                "api_key": self.giphy_api_key,
                "q": query,
                "limit": 1,
                "offset": offset,  # Randomize result
                "rating": "pg-13",
                "lang": "en"
            }
            logger.info(f"Fetching GIF from GIPHY with query: '{query}', offset: {offset}")
            giphy_response = requests.get(self.giphy_api_base, params=params, timeout=5)
            giphy_response.raise_for_status()
            giphy_data = giphy_response.json()

            if not giphy_data["data"]:
                logger.warning(f"No GIFs found for query: {query}. Falling back to random funny GIF.")
                params["q"] = "funny programming fail"
                params["offset"] = random.randint(0, 50)
                giphy_response = requests.get(self.giphy_api_base, params=params, timeout=5)
                giphy_data = giphy_response.json()

            image_url = giphy_data["data"][0]["images"]["original"]["url"] if giphy_data["data"] else "https://media.giphy.com/media/3o6Zt6KHxJTbXCnSso/giphy.gif"
            logger.info(f"GIF fetched: {image_url}")

            return {
                "feedback": feedback,
                "image_url": image_url,
                "situation": situation
            }
        except Exception as e:
            logger.error(f"Error in generate_meme_review: {str(e)}")
            raise Exception(f"Meme generation failed: {str(e)}")