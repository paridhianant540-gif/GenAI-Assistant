import os
import time
import requests
from typing import Tuple, Dict, Any
from app.utils.logger import get_logger

logger = get_logger("llm-service")

class LLMService:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        
        logger.info(f"Initialized LLMService with provider: {self.provider}")
        
    def generate_reply(self, prompt: str, system_instruction: str = "") -> Tuple[str, int]:
        """
        Invokes the selected LLM provider using direct REST requests with built-in retry logic.
        Returns a tuple: (assistant_response_text, tokens_used)
        """
        max_retries = 3
        backoff_factor = 2.0
        
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    return self._call_gemini_api(prompt, system_instruction)
                elif self.provider == "openai":
                    return self._call_openai_api(prompt, system_instruction)
                else:
                    raise ValueError(f"Unsupported LLM provider: {self.provider}")
            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Failed to generate LLM response after maximum retries.")
                    raise e
                time.sleep(backoff_factor ** attempt)

    def _call_gemini_api(self, prompt: str, system_instruction: str) -> Tuple[str, int]:
        """Makes direct HTTP request to Gemini API (verified models/gemini-2.5-flash or models/gemini-1.5-flash)."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
            
        # Enforce verified model: Try gemini-2.5-flash first
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
        active_model = "models/gemini-2.5-flash"
        
        # Payload construction
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        response = requests.post(url, json=payload, timeout=20)
        
        # Fallback to models/gemini-1.5-flash if 2.5-flash is not available in the API key region
        if response.status_code == 404:
            logger.info("gemini-2.5-flash returned 404. Falling back to models/gemini-1.5-flash...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
            active_model = "models/gemini-1.5-flash"
            response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 400:
            err_data = response.json()
            raise ValueError(f"Bad Request: {err_data.get('error', {}).get('message', 'Invalid request parameters.')}")
        elif response.status_code == 403:
            raise PermissionError("Forbidden: Please verify that your GEMINI_API_KEY is valid.")
        elif response.status_code != 200:
            raise RuntimeError(f"Gemini API returned status code {response.status_code}: {response.text}")
            
        data = response.json()
        
        # Extract reply text
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No response candidates returned from Gemini.")
            
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("Response parts empty from Gemini API.")
                
            reply_text = parts[0].get("text", "")
            
            # Extract token counts
            usage = data.get("usageMetadata", {})
            tokens_used = usage.get("totalTokenCount", 0)
            
            return reply_text, tokens_used
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {response.text}")
            raise e

    def _call_openai_api(self, prompt: str, system_instruction: str) -> Tuple[str, int]:
        """Makes direct HTTP request to OpenAI Chat Completions API."""
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set. Please configure it in your .env file.")
            
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 401:
            raise PermissionError("Unauthorized: Please verify that your OPENAI_API_KEY is correct.")
        elif response.status_code != 200:
            raise RuntimeError(f"OpenAI API returned status code {response.status_code}: {response.text}")
            
        data = response.json()
        
        try:
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No answer choice returned from OpenAI.")
                
            reply_text = choices[0].get("message", {}).get("content", "")
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            
            return reply_text, tokens_used
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {response.text}")
            raise e
