"""Similitud de texto para la deduplicación (research R1). Interfaz `SimilarityProvider`.

- `tfidf` (por defecto): n-gramas de caracteres 3–5, sin descargas, tolerante a errores de SMS.
- `minilm` (opcional): embeddings multilingües si `sentence-transformers` está instalado;
  si no, cae a `tfidf` sin romper nada (principio II).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.sms import CODES
from app.core.text import normalize

log = logging.getLogger("dacora.similarity")

_SMS_HEAD_RE = re.compile(
    rf"^dacora\s+(?:(?:{'|'.join(c.lower() for c in CODES)})\s+)?", re.IGNORECASE
)


def clean_for_similarity(text: str) -> str:
    """Quita el prefijo/código de SMS y los marcadores de redacción antes de comparar."""
    return normalize(_SMS_HEAD_RE.sub("", normalize(text, expand=False)))


class SimilarityProvider(Protocol):
    name: str

    def similarities(self, text: str, candidates: list[str]) -> list[float]: ...


class TfidfSimilarity:
    name = "tfidf"

    def similarities(self, text: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        docs = [clean_for_similarity(t) for t in [text, *candidates]]
        if not docs[0].strip():
            return [0.0] * len(candidates)
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        try:
            matrix = vectorizer.fit_transform(docs)
        except ValueError:  # vocabulario vacío
            return [0.0] * len(candidates)
        scores: Any = cosine_similarity(matrix[0:1], matrix[1:])[0]
        return [float(s) for s in scores]


class MiniLmSimilarity:
    name = "minilm"
    MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # importación perezosa

        self._model: Any = SentenceTransformer(self.MODEL)

    def similarities(self, text: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        docs = [clean_for_similarity(t) for t in [text, *candidates]]
        emb: Any = self._model.encode(docs, normalize_embeddings=True)
        return [float(s) for s in (emb[1:] @ emb[0])]


def build_provider(name: str) -> SimilarityProvider:
    if name == "minilm":
        try:
            return MiniLmSimilarity()
        except Exception as exc:  # noqa: BLE001 - degradación controlada
            log.warning("MiniLM no disponible (%s); se usa TF-IDF", exc)
    return TfidfSimilarity()
