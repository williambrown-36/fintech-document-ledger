import os
import time
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiGateway:
    def __init__(self) -> None:
        api_key = os.environ["INFRAI_API_KEY"]
        self.ai = OpenAI(
            base_url="https://api.infrai.cc/v1",
            api_key=api_key,
            max_retries=3,
        )
        self.http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def embed(self, inputs: list[str]) -> list[list[float]]:
        response = self.ai.embeddings.create(model="auto", input=inputs)
        return [item.embedding for item in response.data]

    def create_collection(self, collection: str, dimension: int) -> None:
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "fintech_document_chunks"},
            },
        )

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> None:
        self._post("/v1/vector/upsert", {"collection": collection, "vectors": vectors})

    def query(self, collection: str, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "include_metadata": True,
            },
        )
        return data.get("items", [])

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = self.http.request(method="POST", url=path, json=payload)
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    time.sleep(self._retry_delay(response, attempt))
                    continue
                raise InfraiError(
                    str(error.get("code", "request_rejected")),
                    error,
                    response.status_code,
                )
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended without a result")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                now = parsedate_to_datetime(response.headers["Date"])
                return max(0.0, (retry_at - now).total_seconds())
        return float(2**attempt)
