import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    index: int


def split_document(document_id: str, text: str, max_words: int = 180) -> list[DocumentChunk]:
    words = text.split()
    chunks: list[DocumentChunk] = []
    for index, start in enumerate(range(0, len(words), max_words)):
        body = " ".join(words[start : start + max_words])
        digest = hashlib.sha256(f"{document_id}:{index}:{body}".encode()).hexdigest()
        chunks.append(DocumentChunk(chunk_id=digest, text=body, index=index))
    return chunks
