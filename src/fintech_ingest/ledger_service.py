from .contracts import IngestRequest, IngestResult, SearchResult
from .document_chunks import split_document
from .infrai_gateway import InfraiGateway
from .risk_policy import decide_action

COLLECTION = "fintech_documents"


class LedgerService:
    def __init__(self, gateway: InfraiGateway) -> None:
        self.gateway = gateway

    def ingest(self, request: IngestRequest) -> IngestResult:
        chunks = split_document(request.document_id, request.text)
        embeddings = self.gateway.embed([chunk.text for chunk in chunks])
        self.gateway.create_collection(COLLECTION, len(embeddings[0]))
        vectors = [
            {
                "id": chunk.chunk_id,
                "embedding": embedding,
                "metadata": {
                    "document_id": request.document_id,
                    "chunk_index": chunk.index,
                    "event_id": request.payment.event_id,
                    "text": chunk.text,
                },
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self.gateway.upsert(COLLECTION, vectors)
        return IngestResult(
            document_id=request.document_id,
            chunks_written=len(vectors),
            notification=decide_action(request.payment),
        )

    def search(self, query: str, top_k: int) -> SearchResult:
        query_embedding = self.gateway.embed([query])[0]
        return SearchResult(items=self.gateway.query(COLLECTION, query_embedding, top_k))
