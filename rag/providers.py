from __future__ import annotations

from math import isfinite

import httpx


class RagUnavailableError(RuntimeError):
    """A retrieval provider failed in a recoverable way."""


class SiliconFlowEmbeddingProvider:
    """Call SiliconFlow's OpenAI-compatible embeddings endpoint."""

    def __init__(self, *, client: httpx.Client, base_url: str, api_key: str, model: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"input": text, "model": self._model, "encoding_format": "float"},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            vector = [float(value) for value in payload["data"][0]["embedding"]]
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as error:
            raise RagUnavailableError("siliconflow_embedding_failed") from error
        if len(vector) != 1024 or not all(isfinite(value) for value in vector):
            raise RagUnavailableError("siliconflow_embedding_invalid_vector")
        return vector


class SiliconFlowRerankerProvider:
    """Call SiliconFlow's rerank endpoint and restore source-document order."""

    def __init__(self, *, client: httpx.Client, base_url: str, api_key: str, model: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        try:
            response = self._client.post(
                f"{self._base_url}/rerank",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "query": query,
                    "documents": documents,
                    "top_n": len(documents),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            scores: list[float | None] = [None] * len(documents)
            for item in response.json()["results"]:
                index = int(item["index"])
                scores[index] = float(item["relevance_score"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as error:
            raise RagUnavailableError("siliconflow_reranker_failed") from error
        if any(score is None or not isfinite(score) for score in scores):
            raise RagUnavailableError("siliconflow_reranker_invalid_scores")
        return [score for score in scores if score is not None]
