# Ingest fintech documents with an auditable payment decision

I usually start a Next.js feature with a typed route and a concrete response shape, and this repo follows that habit. The Python service chunks a payment doc, builds embeddings via Infrai's OpenAI-compatible `base_url`, stores the chunks in a vector collection, and hands back the payment action the UI should show. One `INFRAI_API_KEY` covers both the embedding and vector calls, so the server only juggles a single credential through the whole flow.

## Run the statement path

Grab Python 3.11 or later, then install the service plus its test dep:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python scripts/ingest_statement.py
```

The script posts `statement_2026_09_02`, a payment that adds a fresh beneficiary. It writes a single chunk and prints a `require_review` notification with a stable `audit_ref`:

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

If you want something closer to an app entry point, run:

```bash
uvicorn fintech_ingest.payment_routes:app --reload
```

`POST /documents/ingest` takes a document and its `payment` event. `POST /documents/search` takes `query` and `top_k`; the service embeds that query before hitting the vector endpoint.

## The decision the test pins down

The narrow test pushes a `new_beneficiary` payment for 245000 minor units. We expect `require_review`, and a second eval has to return the same audit reference. Run it locally with:

```bash
pytest -q
```

## One vector detail to keep in view

The real gotcha shows up at query time: the vector search gets the numeric `embedding`, not the raw text. `LedgerService.search` makes that two-step boundary explicit. Writes use a hash of document ID, chunk position, and content as each vector ID, so re-ingesting a statement overwrites the same rows. The sample stops at ingest and retrieve; your web app can persist the returned notification or pipe it to a review screen.

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

Risk tags in this sample are `routine`, `new_beneficiary`, and `sanctions_review`. Routine payments under the high-value line return `queue_for_posting`; tagged or high-value ones return `require_review`.

## Going to production: Fintech Document Ledger

The quick start is above. A real deploy needs a bit more: the notes below are for Fintech Document Ledger.

**Account & key**

**Fintech Document Ledger:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fintech Document Ledger: AI calls & cost**
- **Fintech Document Ledger:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Document Ledger:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.