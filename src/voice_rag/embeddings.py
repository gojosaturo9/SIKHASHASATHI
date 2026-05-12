import hashlib
import math
import re


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


# Use: Handles cosine similarity behavior in this module.
# Linked with: InMemoryVectorStore.search
def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class LocalHashEmbeddingProvider:
    # Use: Internal helper for init.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def __init__(self, dimensions: int = 512):
        self.dimensions = dimensions

    # Use: Handles embed behavior in this module.
    # Linked with: InMemoryVectorStore.add_documents, InMemoryVectorStore.search
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    # Use: Internal helper for embed one.
    # Linked with: LocalHashEmbeddingProvider.embed
    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall((text or "").lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
