# STATUS.md — chapter-pacing-report-cli

## What was built

`pacing_report.py` — a single-file, stdlib-only Python 3.10+ CLI that scans a
markdown manuscript and prints a per-chapter pacing report:

- **Chapter detection** via markdown headings (`--heading-level`, default `##`)
- **Word / paragraph counts** per chapter (code blocks stripped, link text kept)
- **Scene break detection** (`***`, `* * *`, `---`, `___`, `<hr>`)
- **Dialogue-to-narration ratio** (words inside single/double/curly quotes)
- **Opening and closing hook scores (0–3)** with friendly notes: opens with
  dialogue / question / action / punchy short sentence; closes on a question /
  cliffhanger imagery / forward-leaning wording / punchy closer
- **Gentle flags**: long or short chapters vs. book average, saggy middle
  candidates, rushed ending candidates, long chapters with no scene breaks,
  narration-heavy or all-dialogue chapters, slow openings, soft landings
- **JSON output** (`--json`) for tooling
- **Optional LLM summaries** (`--llm BASE_URL --model NAME`) against any
  OpenAI-compatible endpoint, including Ollama (`http://localhost:11434/v1`).
  Sends only ~1,200 characters of excerpt per chapter; the API key is read
  from an env var (`--api-key-env`, default `OPENAI_API_KEY`) and never stored
  in any file; requests omit `Authorization` entirely when no key is set,
  which is what Ollama expects.

Deliberately scoped as the *pacing* sibling of chapter-critique-cli (deep
craft critique) and audiobook-length-estimator-cli (audio-hours estimates).

## How to run

```bash
python3 pacing_report.py manuscript.md                 # text report
python3 pacing_report.py manuscript.md --json          # JSON output
python3 pacing_report.py manuscript.md --heading-level 1   # '# Chapter' style
python3 pacing_report.py manuscript.md --llm http://localhost:11434/v1 --model llama3.2
python3 -m pytest test_pacing_report.py -v             # test suite
```

## Verification results

- `python3 -m pytest test_pacing_report.py` — **23/23 tests pass**
  (covers word counting, dialogue extraction incl. curly quotes, chapter
  splitting + fallback, code-block exclusion, hook scoring incl. empty bodies,
  saggy-middle/rushed-ending flag logic, healthy-book no-flags case, JSON
  serializability)
- CLI smoke test on a 3-chapter sample manuscript — correct counts, ratios,
  hook notes, flags, and error paths (missing file → exit 2, no chapters →
  exit 1)
- LLM path verified against a local OpenAI-compatible mock server: correct
  endpoint (`/v1/chat/completions`), payload, and no `Authorization` header
  when no key env var is set
- `py_compile` clean; `--version` reports `pacing_report 1.0.0`

## Known gaps

- Hook scoring is heuristic (word/list-based); stylistically subtle hooks
  (e.g. a strong sensory image opener) won't be credited
- Dialogue ratio counts words inside quote spans, not speaker attribution,
  so heavy quote-attribution prose slightly inflates dialogue share
- Chapter detection assumes one heading style per manuscript; mixed heading
  levels (e.g. `#` part titles interleaved with `##` chapters with the default
  level 2) treat `#` lines as body text
- LLM call failures degrade gracefully to a one-line error note per chapter
  but there is no retry/backoff
- No `setext`-style heading support or `.docx` input (markdown only)
