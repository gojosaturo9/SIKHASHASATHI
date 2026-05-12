from dataclasses import dataclass

from src.voice_rag.documents import Document
from src.voice_rag.embeddings import cosine_similarity


@dataclass
class RetrievedDocument:
    document: Document
    score: float


class InMemoryVectorStore:
    # Use: Internal helper for init.
    # Linked with: Streamlit UI, decorators, tests, or external runtime calls.
    def __init__(self, embedding_provider):
        self.embedding_provider = embedding_provider
        self._documents: list[Document] = []
        self._embeddings: list[list[float]] = []

    # Use: Handles add documents behavior in this module.
    # Linked with: VoiceRAGPipeline.answer
    def add_documents(self, documents: list[Document]):
        if not documents:
            return
        embeddings = self.embedding_provider.embed([doc.text for doc in documents])
        self._documents.extend(documents)
        self._embeddings.extend(embeddings)

    # Use: Handles search behavior in this module.
    # Linked with: VoiceRAGPipeline.answer, _answer_table_rows, _student_by_enrollment_text, poll_inbound_email_replies
    def search(self, query: str, top_k: int = 8) -> list[RetrievedDocument]:
        if not self._documents:
            return []

        query_embedding = self.embedding_provider.embed([query])[0]
        scored = [
            RetrievedDocument(document=doc, score=cosine_similarity(query_embedding, emb))
            for doc, emb in zip(self._documents, self._embeddings)
        ]
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
