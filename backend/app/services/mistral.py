import asyncio
import json
from typing import AsyncGenerator, Optional
import httpx
from app.config import settings


class MistralService:
    """Service for interacting with NVIDIA/Mistral-compatible API."""

    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.base_url = settings.MISTRAL_BASE_URL
        self.chat_model = settings.MISTRAL_CHAT_MODEL
        self.embedding_model = settings.MISTRAL_EMBEDDING_MODEL

    async def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        ) as client:
            payload = {
                "model": model or self.chat_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat_completion_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        ) as client:
            payload = {
                "model": model or self.chat_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def get_embeddings(
        self, texts: list[str], model: Optional[str] = None, input_type: str = "passage"
    ) -> list[list[float]]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        ) as client:
            all_embeddings = []
            batch_size = 20
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {
                    "model": model or self.embedding_model,
                    "input": batch,
                    "input_type": input_type,
                }
                response = await client.post("/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(embeddings)
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            return all_embeddings


_mistral_instance: Optional[MistralService] = None


def get_mistral_service() -> MistralService:
    global _mistral_instance
    if _mistral_instance is None:
        _mistral_instance = MistralService()
    return _mistral_instance
