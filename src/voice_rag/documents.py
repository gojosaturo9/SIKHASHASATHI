import json
import re
from dataclasses import dataclass, field


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


def clean_text(value) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def json_to_documents(value, source: str, metadata=None) -> list[Document]:
    metadata = metadata or {}
    documents = []

    def walk(node, path):
        if isinstance(node, dict):
            if node:
                compact = json.dumps(node, ensure_ascii=True, default=str)
                documents.append(
                    Document(
                        text=f"{path or source}: {compact}",
                        metadata={**metadata, "source": source, "path": path or source},
                    )
                )
            for key, val in node.items():
                walk(val, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for idx, val in enumerate(node):
                walk(val, f"{path}[{idx}]")
        else:
            text = clean_text(node)
            if text:
                documents.append(
                    Document(
                        text=f"{path}: {text}",
                        metadata={**metadata, "source": source, "path": path},
                    )
                )

    walk(value, "")
    return documents


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 900,
    chunk_overlap: int = 160,
) -> list[Document]:
    chunks = []
    step = max(1, chunk_size - chunk_overlap)

    for doc in documents:
        text = clean_text(doc.text)
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append(doc)
            continue

        for idx, start in enumerate(range(0, len(text), step)):
            chunk = text[start : start + chunk_size].strip()
            if chunk:
                chunks.append(
                    Document(
                        text=chunk,
                        metadata={**doc.metadata, "chunk": idx},
                    )
                )
            if start + chunk_size >= len(text):
                break

    return chunks
