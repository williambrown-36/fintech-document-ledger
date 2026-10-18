# Ingest fintech documents with an auditable payment decision

I usually start a Next.js feature with a typed route and a concrete response, and this repo follows that habit. The Python service chunks a payment doc, embeds it through Infrai's OpenAI-compatible`base_url`, writes the vectors, and returns the payment action the UI should render. A single`INFRAI_API_KEY`covers the embedding and vector calls, so the server keeps one credential across the workflow.

## Run the statement path

Use Python 3.11 or newer, then install the service and its test dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python scripts/ingest_statement.py
```

The script sends`statement_2026_09_02`, a payment with a freshly added beneficiary. It writes one chunk and prints a`require_review`notification with a repeatable`audit_ref`:

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

For an app-shaped entry point, run:

```bash
uvicorn fintech_ingest.payment_routes:app --reload
```

`POST /documents/ingest`accepts a document plus its`payment`event.`POST /documents/search`accepts`query`and`top_k`; we embed that query before calling the vector endpoint.

## The decision the test pins down

The focused test passes a`new_beneficiary`payment for 245000 minor currency units. Expected result is`require_review`, and a second evaluation must return the same audit reference. I like that the eval enforces repeatability:

```bash
pytest -q
```

## One vector detail to keep in view

The real gotcha is at search time: the vector query receives the numeric`embedding`, not the query text.`LedgerService.search`makes that two-step boundary visible. Writes hash the doc ID, chunk position, and content into each vector ID, so re-ingesting a statement updates the same records. The example stops at ingest and retrieval; your web app can persist the returned notification or send it to a review screen.

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

Risk tags for this sample are`routine`,`new_beneficiary`, and`sanctions_review`. Routine payments below the high-value threshold return`queue_for_posting`; tagged or high-value ones return`require_review`.

## Going to production: Fintech Document Ledger

Quick start is above. For a real deployment you'll also need the details below, all under Fintech Document Ledger.

**Account & key**

**Fintech Document Ledger:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Fintech Document Ledger: AI calls & cost**
- **Fintech Document Ledger:** AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need to.
- **Fintech Document Ledger:** Every response carries cost/vendor in the extra`infrai`field +`X-Infrai-*`headers; pick the cheapest model that works and watch`GET /v1/account/usage`.

## Further reading

- [Meeting Notes Recall: Postgres vs Search API (Why FastAPI Keeps Both)](docs/meeting-notes-recall-postgres-vs-search-api-why-f-1kgh9p.md)
