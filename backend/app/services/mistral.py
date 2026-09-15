import asyncio
import json
from typing import AsyncGenerator, Optional
import httpx
from app.config import settings

# Maximum retries on 429 / 5xx before giving up
_MAX_RETRIES = 3
_RETRY_BACKOFF = [2, 5, 10]  # seconds between attempts


def _should_retry(status: int) -> bool:
    return status in (429, 500, 502, 503, 504)


class MistralService:
    """Service for interacting with the Mistral API.

    Automatically retries on 429 (rate limit) and transient 5xx errors
    with exponential back-off so the UI never shows raw HTTP errors.
    """

    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.base_url = settings.MISTRAL_BASE_URL
        self.chat_model = settings.MISTRAL_CHAT_MODEL
        self.embedding_model = settings.MISTRAL_EMBEDDING_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ─── Chat completion (non-streaming) ──────────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: Optional[list] = None,
    ) -> dict:
        payload: dict = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        last_err: Exception = RuntimeError("No attempts made")
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    headers=self._headers(),
                    timeout=httpx.Timeout(120.0, connect=10.0),
                ) as client:
                    resp = await client.post("/chat/completions", json=payload)
                    if _should_retry(resp.status_code) and attempt < _MAX_RETRIES - 1:
                        wait = _RETRY_BACKOFF[attempt]
                        print(f"[WARN] Mistral {resp.status_code} on attempt {attempt+1}, retrying in {wait}s…")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                last_err = e
                if _should_retry(e.response.status_code) and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF[attempt]
                    print(f"[WARN] Mistral {e.response.status_code} on attempt {attempt+1}, retrying in {wait}s…")
                    await asyncio.sleep(wait)
                else:
                    raise
            except Exception as e:
                last_err = e
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_RETRY_BACKOFF[attempt])
                else:
                    raise
        raise last_err

    # ─── Streaming chat ────────────────────────────────────────────────────────

    async def chat_completion_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    headers=self._headers(),
                    timeout=httpx.Timeout(120.0, connect=10.0),
                ) as client:
                    async with client.stream("POST", "/chat/completions", json=payload) as response:
                        if _should_retry(response.status_code) and attempt < _MAX_RETRIES - 1:
                            wait = _RETRY_BACKOFF[attempt]
                            print(f"[WARN] Mistral stream {response.status_code} on attempt {attempt+1}, retrying in {wait}s…")
                            await asyncio.sleep(wait)
                            continue
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data.strip() == "[DONE]":
                                    return
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        yield delta["content"]
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                        return  # stream finished successfully
            except httpx.HTTPStatusError as e:
                if _should_retry(e.response.status_code) and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF[attempt]
                    print(f"[WARN] Mistral stream {e.response.status_code} on attempt {attempt+1}, retrying in {wait}s…")
                    await asyncio.sleep(wait)
                else:
                    raise
            except Exception:
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_RETRY_BACKOFF[attempt])
                else:
                    raise

    # ─── Embeddings ────────────────────────────────────────────────────────────

    async def get_embeddings(
        self, texts: list[str], model: Optional[str] = None
    ) -> list[list[float]]:
        """Get embeddings. mistral-embed returns 1024-dim vectors."""
        all_embeddings: list[list[float]] = []
        batch_size = 20

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "model": model or self.embedding_model,
                "input": batch,
            }
            for attempt in range(_MAX_RETRIES):
                try:
                    async with httpx.AsyncClient(
                        base_url=self.base_url,
                        headers=self._headers(),
                        timeout=httpx.Timeout(120.0, connect=10.0),
                    ) as client:
                        resp = await client.post("/embeddings", json=payload)
                        if _should_retry(resp.status_code) and attempt < _MAX_RETRIES - 1:
                            await asyncio.sleep(_RETRY_BACKOFF[attempt])
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        embeddings = [item["embedding"] for item in data["data"]]
                        all_embeddings.extend(embeddings)
                        break
                except httpx.HTTPStatusError as e:
                    if _should_retry(e.response.status_code) and attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_RETRY_BACKOFF[attempt])
                    else:
                        raise
                except Exception:
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_RETRY_BACKOFF[attempt])
                    else:
                        raise

            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        return all_embeddings

    async def close(self):
        pass  # per-request clients — nothing to close


_mistral_instance: Optional[MistralService] = None


def get_mistral_service() -> MistralService:
    global _mistral_instance
    if _mistral_instance is None:
        _mistral_instance = MistralService()
    return _mistral_instance
