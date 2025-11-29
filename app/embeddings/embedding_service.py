from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generate embeddings locally with SentenceTransformers.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode([text], convert_to_numpy=True)[0]

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


class VectorStoreManager:
    """
    Minimal persistent vector store backed by NumPy arrays.
    """

    def __init__(self, persist_directory: Path):
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.vectors_path = self.persist_directory / "vectors.npz"
        self.meta_path = self.persist_directory / "meta.json"
        self._resume_lookup: Dict[str, Dict] = {}
        self._vectors = np.zeros((0, 384), dtype=np.float32)
        self._metadatas: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if self.vectors_path.exists() and self.meta_path.exists():
            try:
                data = np.load(self.vectors_path)
                self._vectors = data["vectors"]
                with open(self.meta_path, "r", encoding="utf-8") as meta_file:
                    self._metadatas = json.load(meta_file)
                logger.info("Loaded %s resume embeddings from disk.", len(self._metadatas))
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to load persisted vectors; starting fresh.")
                self._vectors = np.zeros((0, 384), dtype=np.float32)
                self._metadatas = []

    def _persist(self) -> None:
        np.savez_compressed(self.vectors_path, vectors=self._vectors)
        with open(self.meta_path, "w", encoding="utf-8") as meta_file:
            json.dump(self._metadatas, meta_file, ensure_ascii=False, indent=2)

    def build_store(
        self,
        resumes: Iterable[Dict],
        embedding_service: EmbeddingService,
    ) -> None:
        texts: List[str] = []
        metadatas: List[Dict] = []
        self._resume_lookup = {}

        for idx, resume in enumerate(resumes, start=1):
            resume_id = str(idx)
            texts.append(resume["text"])
            metadata = {"candidate_id": resume_id, **resume.get("metadata", {})}
            metadatas.append(metadata)
            self._resume_lookup[resume_id] = resume

        if not texts:
            logger.warning("No resumes supplied for vector store build.")
            self._vectors = np.zeros((0, 384), dtype=np.float32)
            self._metadatas = []
            return

        embeddings = embedding_service.embed_documents(texts)
        self._vectors = embeddings.astype(np.float32)
        self._metadatas = metadatas
        self._persist()
        logger.info("Vector store built with %s resumes.", len(texts))

    def similarity_search_with_scores(
        self, query_vector: np.ndarray, k: int | None = None
    ) -> List[Tuple[Dict, float]]:
        if self._vectors.size == 0:
            raise RuntimeError("Vector store is not initialized.")

        sims = cosine_similarity(query_vector.reshape(1, -1), self._vectors)[0]
        order = np.argsort(-sims)
        if k:
            order = order[:k]

        results: List[Tuple[Dict, float]] = []
        for idx in order:
            metadata = self._metadatas[idx]
            distance = 1 - float(sims[idx])  # reuse distance-based scoring
            results.append((metadata, distance))
        return results

    def get_resume_by_id(self, resume_id: str) -> Dict | None:
        return self._resume_lookup.get(resume_id)

