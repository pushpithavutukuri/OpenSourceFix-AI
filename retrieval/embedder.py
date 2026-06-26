"""
embedder.py

Encodes text (code chunks or issue descriptions) into dense vectors
using the BGE-small-en-v1.5 model from sentence-transformers.

Why BGE?
    - State-of-the-art retrieval performance on code + text
    - Runs locally (no API cost, no rate limits)
    - 384-dim vectors → fast FAISS search even at 100k chunks
    - BGE instruction prefix boosts retrieval accuracy

Model choice:
    BAAI/bge-small-en-v1.5   ← default (fast, 33M params, good accuracy)
    BAAI/bge-base-en-v1.5    ← better accuracy, 110M params
    BAAI/bge-large-en-v1.5   ← best accuracy, 335M params (slow on CPU)
"""

import logging
import numpy as np
from typing import List, Union

logger = logging.getLogger(__name__)

# BGE retrieval instruction prefix (improves recall for asymmetric search)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    """
    Thin wrapper around SentenceTransformer for BGE models.

    Usage:
        embedder = Embedder()
        code_vecs  = embedder.embed_corpus(["def login(): ...", "class Session: ..."])
        query_vecs = embedder.embed_query("login fails after session timeout")
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", device: str = "cpu"):
        """
        Args:
            model_name: HuggingFace model ID.
            device:     "cpu" or "cuda" (auto-detected if not specified).
        """
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s on %s", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info("Embedder ready — vector dim: %d", self._dim)

    @property
    def dim(self) -> int:
        return self._dim

    def embed_corpus(
        self,
        texts: List[str],
        batch_size: int = 64,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Embed a list of code/document strings (no instruction prefix).

        Args:
            texts:         List of strings to embed.
            batch_size:    How many to encode at once (tune for your GPU/CPU RAM).
            show_progress: Show tqdm progress bar.

        Returns:
            np.ndarray of shape (len(texts), dim), dtype float32.
        """
        logger.info("Embedding %d corpus chunks...", len(texts))
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,   # cosine similarity = dot product
            convert_to_numpy=True,
        )
        return vectors.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string WITH the BGE instruction prefix.

        The prefix asymmetry (query has it, corpus doesn't) is the
        standard BGE setup and improves retrieval accuracy.

        Returns:
            np.ndarray of shape (1, dim), dtype float32.
        """
        prefixed = BGE_QUERY_PREFIX + query
        vector = self._model.encode(
            [prefixed],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vector.astype(np.float32)
