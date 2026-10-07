# Vocairo Text Analyzer

FastAPI service for plain-text, EPUB, subtitle, word-enrichment, and translation
analysis. It is consumed by the NestJS backend and runs locally on port 8080.
The reserved image routes report `503` until a production OCR adapter exists.

## Local Development

```bash
cd /Users/oleks/Work/Vocairo/vocairo_text_analyzer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
python -m nltk.downloader -d "$PWD/.nltk_data" punkt punkt_tab wordnet omw-1.4
export NLTK_DATA="$PWD/.nltk_data"
uvicorn app.main:app --reload --port 8080
```

Runtime code never downloads NLP data. Production and CI use the checksum-
verified corpora baked into the pinned Docker image; the command above is only
the explicit local bootstrap path.

Verify:

```bash
curl http://localhost:8080/health
```

Interactive docs:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Environment

```env
ANALYZER_API_KEY=
DEEPL_API_KEY=
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3006
DEBUG=false
```

## Error Monitoring

Railway deployments report exceptions through Sentry SDK to the separate Better
Stack application **Vocairo Analyzer (2787469)**. Local runs require
`SENTRY_ENABLED=true`; `SENTRY_ENABLED=false` disables reporting on Railway too.
`SENTRY_DSN` overrides the public ingest DSN. Environment/release default to
`RAILWAY_ENVIRONMENT_NAME` and `RAILWAY_GIT_COMMIT_SHA`; explicit overrides use
`SENTRY_ENVIRONMENT` and `SENTRY_RELEASE`.

Only unexpected exceptions and handled HTTP 500 errors are reported. Expected
401/422/503/504 responses (including unavailable OCR/providers) do not create
bug reports. The adapter retains exception types, deployment metadata and source
file/line call sites, and removes messages, users, requests, breadcrumbs, local
variables and source context. Logs, traces, profiles and metrics are disabled.

Run `python -m pytest -q tests/test_monitoring.py` to exercise the actual FastAPI
and SDK pipeline with an in-memory transport. A deployment smoke check must use
`SENTRY_ENVIRONMENT=smoke-test` and the `monitoring_smoke=true` tag, and verify
the event's release and original file/line in Better Stack. Smoke events are
verification records and must not create production bug tasks. Python tracebacks
already contain file/line call sites; JavaScript source-map upload is separate.

## Word Filtering

Text analysis returns candidates in `words` and diagnostic exclusions in
`excluded_words`. Final admission belongs to NestJS, which corroborates morphology,
POS, contextual names and frequency with dictionary sources before creating words.

| Bucket | Rule |
|---|---|
| `accepted` | WordNet or frequency supports a candidate; NestJS still validates it |
| `proper_nouns` | Contextual NER identifies a name and WordNet has no common-word evidence |
| `unknown` | No preliminary lexical support |

Capitalization and frequency alone never identify a proper noun. Ambiguous common
words such as apple remain candidates for NestJS's dictionary/context decision.
NER is statistical and may be wrong; the backend does not treat it as an absolute veto.

```env
WORD_FILTER_ENABLED=true
WORD_FILTER_MIN_WORD_LENGTH=2
WORD_FILTER_MIN_ZIPF=2.0
```

`WORD_FILTER_ENABLED=false` skips this preliminary classification; it does not
bypass NestJS admission. The former capitalization thresholds have been removed.

`POST /api/lexical-evidence` accepts `{text, language, context?: {text, start, end}}`.
Context offsets are Unicode code points; the NestJS adapter converts UTF-16 offsets.
It returns all WordNet lemma candidates, optional Zipf frequency and optional NER
label. English morphology/NER never run under a different language code. Unsupported
wordfreq languages return null frequency. Provider/resource failures return 503.
The Docker image pins and smoke-tests the NLTK models; no runtime downloads occur.

`ANALYZER_API_KEY` is required for every `/api/*` route. Send it in the
`X-API-Key` header; `/health` remains public:

```bash
curl -X POST http://localhost:8080/api/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ANALYZER_API_KEY" \
  -d '{"text":"This sentence is long enough to analyze."}'
```

## Docker

```bash
docker build -t vocairo-text-analyzer .
docker run --rm -p 8080:8080 --env-file .env vocairo-text-analyzer
```

Run the exact CI test environment without network access:

```bash
docker build --target test -t vocairo-text-analyzer:test .
docker run --rm --network none vocairo-text-analyzer:test
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/text` | Analyze plain text |
| `POST` | `/api/epub` | Analyze EPUB files |
| `POST` | `/api/subtitle` | Analyze subtitle files |
| `POST` | `/api/enrich-word` | Fetch word NLP data (legacy-compatible request shape) |
| `GET` | `/api/word/{word}/nlp` | Fetch NLP data for a word |
| `GET` | `/api/word/{word}/phonetics` | Fetch phonetic text and audio |
| `POST` | `/api/translate` | Translate text |
| `POST` | `/api/translate/batch` | Translate a bounded batch |
| `POST` | `/api/translation/validate` | Validate a candidate translation for NestJS |
| `POST` | `/api/image` | Reserved OCR endpoint; returns `503` until a real OCR adapter is configured |
| `GET` | `/api/image/health` | Honest OCR capability status (`503` while unavailable) |

The analyzer is stateless. Database persistence and batch enrichment are owned
by the NestJS API, which calls these analysis endpoints and writes through
Kysely (`POST /admin/words/{id}/reload` and
`POST /admin/words/batch-enrich`).

Active file-analysis endpoints reject a declared oversize body and enforce
`MAX_UPLOAD_BYTES` while reading the already parsed `UploadFile`. In the live
topology, NestJS also caps multipart bodies before forwarding them. A direct
public analyzer deployment must additionally enforce a request-body limit at
its ingress/reverse proxy because Starlette may spool multipart files before
the route reads them.

## Structure

```text
app/
  main.py
  config.py
  dependencies.py
  models/
  processors/
  routers/
  services/
```
