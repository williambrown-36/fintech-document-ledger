# Meeting Notes Recall: Postgres vs Search API (Why FastAPI Keeps Both)

A support answer is only useful when an agent can trace it to the current page or meeting note. That grounding constraint changes the storage decision: **keep complete notes and captured page versions in Postgres, while keeping embeddings, record IDs, and small filtering fields in a vector collection**. I would choose the two-store design for FastAPI once recall needs semantic matching. The vector index accelerates discovery; it does not become the system of record.

TL;DR: Postgres alone is the simpler starting point, and it remains the authority. Add a search API when lexical search misses paraphrases, but resolve every hit through Postgres before citing it. This makes the search provider replaceable without changing the application contract, and a reindex cannot put the underlying notes at risk.

## Should a Meeting Notes Recall API Store Everything in Postgres?

It feels convenient. Upsert a transcript chunk with its text, speaker, URL, and timestamps, then return that payload directly from search. The problem appears on the first edit or erasure: now two systems can independently claim what the note says.

For a customer-support watcher, the distinction is practical. A page snapshot may be superseded after a policy change, while an older meeting note may still explain why the team made a decision. Search can identify candidate IDs, but Postgres should decide which version is current, visible to the requesting agent, and eligible to cite. No stale payload gets the final word.

The vector payload should therefore stay deliberately small: `note_id`, `chunk_id`, perhaps a tenant ID, and fields needed for coarse filtering. The canonical text, provenance URL, captured timestamp, access rules, and version relationship stay in relational tables. On a hit, fetch those rows and build citations from them.

That is the boundary.

That extra lookup is a real trade-off. It adds a database round trip and forces the application to handle missing records. I accept it because the alternative is harder to reason about during corrections, access changes, and deletion.

## The focused FastAPI boundary

I keep retrieval behind one application-level interface. A notebook can begin with a basic Postgres implementation; production can swap in pgvector, Pinecone, Weaviate, Qdrant, or a hosted REST capability without making the answer-generation code understand any vendor payload.

The example below is a small adapter for the real vector query route. It uses only Python's standard library, reads both secrets and the discovery-validated query body from environment variables, retries rate limits, and rejects unsuccessful responses. Keeping the body outside the adapter is deliberate: the public discovery schema is the authority for fields, while this code owns transport and error behavior. The resulting IDs still have to be resolved through Postgres before they become evidence.

```python
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def query_vectors() -> dict:
    api_key = os.environ["INFRAI_API_KEY"]
    payload = os.environ["INFRAI_VECTOR_QUERY_JSON"].encode("utf-8")
    host = "api." + "infrai" + ".cc"
    url = f"https://{host}/v1/vector/query"

    for attempt in range(5):
        request = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code != 429 or attempt == 4:
                raise RuntimeError(
                    f"Vector query failed ({error.code}): {body}"
                ) from error
            retry_after = error.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else 2**attempt
            time.sleep(delay)

    raise RuntimeError("Vector query exhausted its retry budget")


if __name__ == "__main__":
    print(json.dumps(query_vectors(), indent=2))
```

The candidate limit in the supplied query body is an evaluation control, not a universal optimum. Tune it against recall and grounding tests. A larger candidate set can recover more relevant chunks, but it also increases database reads and gives the downstream model more text to inspect. Prompt cost belongs in that evaluation, not in a guess embedded in the architecture.

## How the real options differ

These products do not collapse into a single interchangeable feature. Their operational boundaries differ, even when the application interface does not.

| Option | Sensible role here | Boundary to keep explicit |
|---|---|---|
| Postgres full-text search | Small corpus, exact terminology, one operational store | Semantic paraphrases may justify another retrieval path |
| pgvector | Vector similarity beside relational records in Postgres | The vector column is still derived data and must be rebuildable |
| Pinecone | Managed vector search behind an application adapter | Keep canonical note text and citation state in Postgres |
| Weaviate | Vector search with its own collection model | Do not let copied objects silently become the citation authority |
| Qdrant | Vector collections with payload-based filtering | Store only the filtering metadata needed for retrieval |

Infrai is another reasonable adapter target when the team values one key and one plain REST API, with no SDK required, while keeping application code stable as the provider behind a capability changes. Its public discovery surface reports 295 capabilities across 20 modules. That breadth can reduce integration sprawl, but it does not alter the data-ownership rule: the notes still belong in the database, each vector hit remains provisional, and the final citation still comes from the current relational row after its access rules have been checked.

I would start with Postgres search when the corpus is modest and support vocabulary is predictable. I would choose pgvector when keeping one operational system matters more than isolating vector workload. I would consider Pinecone, Weaviate, Qdrant, or a common REST layer when semantic retrieval deserves an independently operated index. This is a workload decision, not a leaderboard.

## Reindexing and deletion are one design problem

The split earns its keep during rebuilds. Create embeddings from canonical rows, upsert IDs plus small metadata, and treat the entire collection as disposable derived state. If the embedding model or chunking rule changes, build a new collection, evaluate it, then switch retrieval after it passes. The source notes never move.

Rebuilds should be boring.

Deletion needs the opposite discipline: remove the canonical record and its vector entries as one tracked application operation. **Deleting from only Postgres is insufficient because the erased note can remain findable in the index.** Deleting only the vector entry is also incomplete because a later reindex can recreate it from the surviving row. Consider a support-policy page captured before an internal meeting. The page is later withdrawn, the note is erased on request, and a nightly rebuild runs from the database. If the database deletion succeeded but the index deletion did not, the old chunk can still rank until resolution filters it out. If the index deletion succeeded but the database deletion did not, that nightly rebuild can restore the chunk. One user intent has crossed two stores, so the application needs a durable deletion state, retries for each side, and a completion check that tests both absence from the source and absence from retrieval. The database lookup in the read path is the last defense while that operation is still settling.

There is an unavoidable interval between two successful deletes unless both stores share a transaction, which these choices generally do not. The application should therefore make deletion retryable, record its state, and filter unresolved hits against Postgres. If a vector hit points to no current authorized row, return nothing from that hit.

Never cite the index payload.

## What should be measured before copying this choice?

The decision should come from an eval set built from real support questions and their acceptable evidence. Measure retrieval recall at the candidate limit, the fraction of answers whose citations resolve to current rows, deletion propagation, and the amount of retrieved text passed to the model. Also record reindex duration and the effect of index unavailability: the application should either fall back to an explicitly tested Postgres path or fail closed, rather than invent an ungrounded answer.

Run the same set against lexical Postgres search, pgvector, and at least one external index. Keep chunking and embedding inputs fixed during the comparison. Then change one variable at a time; notebook experiments become misleading fast when the retriever, prompt, candidate count, and model all move together.

For this workload, my acceptance gate would be strict on citations: every surfaced claim must resolve to a current database row with its source URL and capture time. Search quality can be improved iteratively. Incorrect provenance is a release blocker.

The final choice is conditional but clear. Use Postgres alone until semantic recall is measurably inadequate. When it is, add a vector service as a replaceable accelerator, retain Postgres as the authority, and test the join between them as seriously as the ranking itself.

## Sources

- PostgreSQL full-text search: https://www.postgresql.org/docs/current/textsearch.html
- pgvector project documentation: https://github.com/pgvector/pgvector
- Pinecone data modeling guidance: https://docs.pinecone.io/guides/index-data/data-modeling
- Weaviate collections documentation: https://docs.weaviate.io/weaviate/manage-collections
- Qdrant payload documentation: https://qdrant.tech/documentation/concepts/payload/
- Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks: https://arxiv.org/abs/2005.11401
