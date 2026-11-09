"""
retriever.py

WHAT THIS FILE IS FOR
----------------------
This interface defines the Retrieval-Augmented Generation (RAG)
retrieval contract.

Given a query or structured context request, implementations retrieve
relevant, citable chunks from an approved vector index. These retrieved
chunks provide evidence that downstream LLM services use to generate
grounded responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source: str  # citable source name/id
    score: float  # similarity score, for debugging/evaluation
    retriever_version: str


@runtime_checkable
class Retriever(Protocol):
    """Abstract contract for semantic search over an approved document/index set."""

    async def retrieve(
        self, query: str, top_k: int = 5, index_name: str | None = None
    ) -> list[RetrievedChunk]:
        """
        Return the top_k most relevant chunks for `query`. `index_name`
        lets callers target a specific approved index (e.g. glossary vs
        securities) when more than one exists.
        """
        ...
