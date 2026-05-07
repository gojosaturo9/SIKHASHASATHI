from dataclasses import dataclass

from src.utils.secrets import get_secret


@dataclass(frozen=True)
class VoiceRAGConfig:
    chat_model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    top_k: int = 8
    chunk_size: int = 900
    chunk_overlap: int = 160
    local_embedding_dimensions: int = 512

    @classmethod
    def from_secrets(cls):
        return cls(
            chat_model=get_secret("GEMINI_MODEL", cls.chat_model),
        )


SYSTEM_PROMPT = (
    "You are a Voice-RAG assistant for an AI attendance platform. "
    "Answer only from the retrieved context provided to you. "
    "Respect role boundaries strictly: admin can see the provided admin data, "
    "teacher can see only their provided class data, and student can see only "
    "their own provided data. If the answer is not present, say that the "
    "permitted records do not contain it. Do not reveal passwords, secrets, "
    "biometric embeddings, or hidden implementation details."
)
