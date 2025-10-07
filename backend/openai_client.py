"""OpenAI Videos API client wrapper."""
from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class OpenAIVideosClient:
    """Thin wrapper over the OpenAI Videos REST API."""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        model: str = "sora-1.0",
        beta_header: str = "video-generation=2",
    ) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.model = model
        self.beta_header = beta_header

    async def create_video(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a video generation job."""

        url = f"{self.api_base}/videos"
        request_body = {"model": self.model, **payload}
        logger.debug("Submitting video creation request: %s", request_body)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_body, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            logger.info("OpenAI video job created: %s", data.get("id"))
            return data

    async def retrieve_video(self, job_id: str) -> Dict[str, Any]:
        """Retrieve the latest status for a video generation job."""

        url = f"{self.api_base}/videos/{job_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            logger.debug("Polled job %s -> %s", job_id, data.get("status"))
            return data

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.beta_header:
            headers["OpenAI-Beta"] = self.beta_header
        return headers
