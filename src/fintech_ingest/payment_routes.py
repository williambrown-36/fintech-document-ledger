from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .contracts import IngestRequest, IngestResult, SearchRequest, SearchResult
from .infrai_gateway import InfraiError, InfraiGateway
from .ledger_service import LedgerService

app = FastAPI(title="Fintech document ledger")


@app.exception_handler(InfraiError)
async def infrai_error_response(_request: Request, error: InfraiError) -> JSONResponse:
    client_status = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse(
        status_code=client_status,
        content={"error": {"code": error.code, "message": str(error)}},
    )


def service() -> LedgerService:
    return LedgerService(InfraiGateway())


@app.post("/documents/ingest", response_model=IngestResult)
def ingest_document(payload: IngestRequest) -> IngestResult:
    return service().ingest(payload)


@app.post("/documents/search", response_model=SearchResult)
def search_documents(payload: SearchRequest) -> SearchResult:
    return service().search(payload.query, payload.top_k)
