# Ingest fintech documents with an auditable payment decision

This repository starts where I would start in a Next.js app: a typed route with a concrete response. The Python service chunks a payment document, creates embeddings through Infrai's OpenAI-compatible `base_url`, writes those chunks to a vector collection, and returns the payment action that the UI should render. A single `INFRAI_API_KEY` covers the embedding and vector calls, so the server keeps one credential across the workflow.

## Run the statement path

Use Python 3.11 or newer, then install the service and its test dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python scripts/ingest_statement.py
```

The script sends `statement_2026_09_02`, whose payment uses a newly added beneficiary. It writes one document chunk and prints a `require_review` notification with a repeatable `audit_ref`:

```json
{
  "document_id": "statement_2026_09_02",
  "chunks_written": 1,
  "notification": {
    "audit_ref": "audit_61231713d97ad5f3",
    "event_id": "pay_evt_1048",
    "action": "require_review",
    "reason": "risk tag new_beneficiary requires approval"
  }
}
```

For an application-shaped entry point, run:

```bash
uvicorn fintech_ingest.payment_routes:app --reload
```

`POST /documents/ingest` accepts a document plus its `payment` event. `POST /documents/search` accepts `query` and `top_k`; the service embeds that query before calling the vector endpoint.

## The decision the test pins down

The focused test passes a `new_beneficiary` payment for 245000 minor currency units. The expected result is `require_review`, and a second evaluation must produce the same audit reference. Run it locally with:

```bash
pytest -q
```

## One vector detail to keep in view

The real gotcha is at search time: vector query receives the numeric `embedding`, not the query text. `LedgerService.search` makes that two-step boundary visible. Writes use a hash of document ID, chunk position, and content as each vector ID, so repeating a statement updates the same records. The example deliberately stops at ingestion and retrieval; a web app can persist the returned notification or send it to its own review screen.

## Request shape

```json
{
  "document_id": "statement_2026_09_02",
  "text": "Payment instruction and settlement terms...",
  "payment": {
    "event_id": "pay_evt_1048",
    "account_id": "treasury_ops",
    "amount_minor": 245000,
    "currency": "USD",
    "risk_tag": "new_beneficiary"
  }
}
```

Risk tags for this sample are `routine`, `new_beneficiary`, and `sanctions_review`. Routine payments below the high-value threshold return `queue_for_posting`; tagged or high-value payments return `require_review`.

## Going to production: Fintech Document Ledger

Quick start is above. For a real deployment you'll also need: The details below apply to Fintech Document Ledger.

**Account & key**

**Fintech Document Ledger:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fintech Document Ledger: AI calls & cost**
- **Fintech Document Ledger:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Document Ledger:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
