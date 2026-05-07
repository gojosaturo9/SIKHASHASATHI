from dataclasses import dataclass

from src.voice_rag.config import VoiceRAGConfig
from src.voice_rag.documents import Document, chunk_documents
from src.voice_rag.embeddings import (
    LocalHashEmbeddingProvider,
)
from src.voice_rag.llm import DashboardAnswerer, GeminiChatClient
from src.voice_rag.vector_store import InMemoryVectorStore, RetrievedDocument


@dataclass
class RAGResponse:
    question: str
    answer: str
    retrieved: list[RetrievedDocument]
    transcript: str | None = None
    audio: bytes | None = None


class VoiceRAGPipeline:
    def __init__(self, config: VoiceRAGConfig | None = None):
        self.config = config or VoiceRAGConfig.from_secrets()
        local_embeddings = LocalHashEmbeddingProvider(
            dimensions=self.config.local_embedding_dimensions
        )
        self.embedding_provider = local_embeddings
        self.chat_client = GeminiChatClient(
            model=self.config.chat_model,
            temperature=self.config.temperature,
        )
        self.dashboard_answerer = DashboardAnswerer()

    def answer(
        self,
        role: str,
        question: str,
        documents: list[Document],
        dashboard_context: dict | None = None,
        speak: bool = False,
    ) -> RAGResponse:
        chunks = chunk_documents(
            documents,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        store = InMemoryVectorStore(self.embedding_provider)
        store.add_documents(chunks)
        retrieved = store.search(question, top_k=self.config.top_k)
        context = self._format_context(retrieved)

        answer = self.chat_client.answer(role=role, question=question, context=context)
        if not answer:
            answer = self.dashboard_answerer.answer(
                role, question, dashboard_context, retrieved
            )

        audio = None
        return RAGResponse(question=question, answer=answer, retrieved=retrieved, audio=audio)

    def answer_audio(
        self,
        role: str,
        audio_bytes: bytes,
        documents: list[Document],
        dashboard_context: dict | None = None,
        filename: str = "question.wav",
        speak: bool = True,
    ) -> RAGResponse:
        transcript = self._transcribe_audio_with_gemini(audio_bytes, filename)
        if not transcript:
            details = self.chat_client.last_error or "No transcript was returned."
            return RAGResponse(
                question="",
                transcript=None,
                answer=(
                    "I could not transcribe that audio. Make sure `.env` contains "
                    "`GEMINI_API_KEY`, then check the microphone recording or upload "
                    f"a clear WAV/MP3/M4A file. Details: {details}"
                ),
                retrieved=[],
            )

        response = self.answer(
            role=role,
            question=transcript,
            documents=documents,
            dashboard_context=dashboard_context,
            speak=False,
        )
        response.transcript = transcript
        return response

    def _transcribe_audio_with_gemini(self, audio_bytes: bytes, filename: str) -> str | None:
        if not audio_bytes:
            self.chat_client.last_error = "Audio input was empty."
            return None
        if not self.chat_client.api_key:
            self.chat_client.last_error = "GEMINI_API_KEY is not configured."
            return None

        import mimetypes

        try:
            from google import genai
            from google.genai import types

            mime_type = mimetypes.guess_type(filename or "question.wav")[0] or "audio/wav"
            client = genai.Client(api_key=self.chat_client.api_key)
            response = client.models.generate_content(
                model=self.config.chat_model,
                contents=[
                    "Transcribe this audio question exactly. Return only the transcript.",
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                ],
            )
            transcript = (response.text or "").strip().strip('"')
            return transcript or None
        except Exception as exc:
            self.chat_client.last_error = str(exc)
            return None

    @staticmethod
    def _format_context(retrieved: list[RetrievedDocument]) -> str:
        if not retrieved:
            return "No relevant permitted records were retrieved."
        lines = []
        for index, item in enumerate(retrieved, start=1):
            path = item.document.metadata.get("path", "record")
            lines.append(f"[{index}] score={item.score:.3f} path={path}\n{item.document.text}")
        return "\n\n".join(lines)
