from dataclasses import dataclass

from src.utils.secrets import get_secret


@dataclass(frozen=True)
class VoiceRAGConfig:
    provider: str = "gemini" # "gemini" or "openai"
    chat_model: str = "gemini-2.0-flash"
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.2
    top_k: int = 8
    chunk_size: int = 900
    chunk_overlap: int = 160
    local_embedding_dimensions: int = 512

    # Use: Handles from secrets behavior in this module.
    # Linked with: VoiceRAGPipeline.__init__
    @classmethod
    def from_secrets(cls):
        return cls(
            provider=get_secret("CHAT_PROVIDER", "gemini"),
            chat_model=get_secret("GEMINI_MODEL", "gemini-2.0-flash"),
            openai_model=get_secret("OPENAI_MODEL", "gpt-4o-mini"),
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
