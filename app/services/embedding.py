import os
import time
import requests
from typing import List
from app.utils.logger import get_logger

logger = get_logger("embedding-service")

class EmbeddingService:
    def __init__(self):
        self.provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        
        logger.info(f"Initialized EmbeddingService with provider: {self.provider}")
        
    def generate_embedding(self, text: str) -> List[float]:
        """Generates a dense vector embedding for the given text with error handling and retries."""
        if not text:
            raise ValueError("Input text for embedding cannot be empty.")
            
        max_retries = 3
        backoff_factor = 2.0
        
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    return self._get_gemini_embedding(text)
                elif self.provider == "openai":
                    return self._get_openai_embedding(text)
                else:
                    raise ValueError(f"Unsupported embedding provider: {self.provider}")
            except Exception as e:
                logger.warning(f"Embedding generation attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Failed to generate embedding after maximum retries.")
                    raise e
                time.sleep(backoff_factor ** attempt)

    def _get_gemini_embedding(self, text: str) -> List[float]:
        """Calls Google Generative AI REST API to fetch embedding, using verified model names."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
            
        # Try models/gemini-embedding-2 first (Latest state-of-the-art embedding)
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-embedding-2:embedContent?key={self.gemini_key}"
            payload = {
                "model": "models/gemini-embedding-2",
                "content": {
                    "parts": [{"text": text}]
                }
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data["embedding"]["values"]
            else:
                logger.warning(f"models/gemini-embedding-2 returned status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.warning(f"Failed to use gemini-embedding-2: {str(e)}")

        # Fallback to models/gemini-embedding-001 which is globally available and extremely stable
        logger.info("Falling back to standard models/gemini-embedding-001 embedding model...")
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-embedding-001:embedContent?key={self.gemini_key}"
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{"text": text}]
            }
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 400:
            err_data = response.json()
            raise ValueError(f"Bad Request: {err_data.get('error', {}).get('message', 'Invalid request parameters.')}")
        elif response.status_code == 403:
            raise PermissionError("Forbidden: Please verify that your GEMINI_API_KEY is valid.")
        elif response.status_code != 200:
            raise RuntimeError(f"Gemini API returned status code {response.status_code}: {response.text}")
            
        data = response.json()
        embedding = data.get("embedding", {}).get("values")
        if not embedding:
            raise ValueError("Embeddings values not found in Gemini API response.")
            
        return embedding

    def _get_openai_embedding(self, text: str) -> List[float]:
        """Calls OpenAI REST API to fetch text-embedding-3-small embedding."""
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set. Please configure it in your .env file.")
            
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": text,
            "model": "text-embedding-3-small"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 401:
            raise PermissionError("Unauthorized: Please verify that your OPENAI_API_KEY is correct.")
        elif response.status_code != 200:
            raise RuntimeError(f"OpenAI API returned status code {response.status_code}: {response.text}")
            
        data = response.json()
        embedding = data.get("data", [{}])[0].get("embedding")
        if not embedding:
            raise ValueError("Embeddings values not found in OpenAI API response.")
            
        return embedding
