# chapter-pacing-report-cli

A chapter pacing checkup for authors. Scan a markdown manuscript and get a
per-chapter report on word counts, scene breaks, dialogue-to-narration ratio,
and opening/closing hooks — plus gentle flags like "saggy middle" or "rushed
ending," phrased the way a kind writing buddy would.

Built by [Asdale Dynamics, LLC](https://dylanasdale.github.io) as part of a
collection of plain-English, local-first tools for authors.

## How it's different from sibling tools

| Tool | Focus |
|---|---|
| **chapter-pacing-report-cli** (this one) | Per-chapter *pacing*: rhythm, scene breaks, hooks, gentle flags |
| chapter-critique-cli | Deep per-chapter *critique*: prose quality, craft feedback |
| audiobook-length-estimator-cli | Total *audio hours* and runtime estimates |

## Quick start

```bash
python3 pacing_report.py manuscript.md
```

That's it — no dependencies beyond Python 3.10+.

## Example output

```text
Chapter Pacing Report
============================================================
Chapters: 3  |  Words: 308  |  Scene breaks: 1  |  Dialogue: 16%

Chapter 1: The Wreck
  Words: 95  Paragraphs: 6  Scene breaks: 1
  Dialogue: 10% (9 of 95 words)
  Opening hook (2/3): opens with dialogue, short punchy opener
  Closing hook (1/3): short punchy closer
```

## Options

| Flag | Meaning |
|---|---|
| `manuscript` | Path to your markdown manuscript |
| `--heading-level {1,2,3}` | Heading level that marks a chapter (default `2`, i.e. `## Chapter Title`) |
| `--json` | Machine-readable JSON output instead of the text report |
| `--llm BASE_URL` | Optional: ask an OpenAI-compatible endpoint for a one-line per-chapter pacing note |
| `--model NAME` | Model name for `--llm` (default: `llama3.2`) |
| `--api-key-env VAR` | Env var holding the API key (default: `OPENAI_API_KEY`) |
| `--timeout SECONDS` | HTTP timeout for LLM calls (default: `120`) |

### Chapter detection

By default, every `## Heading` starts a new chapter. Writing chapters as
`# Chapter One` instead? Use `--heading-level 1`.

### Optional LLM summaries (works great with Ollama)

Run a local model with Ollama, then point the tool at it:

```bash
ollama serve
ollama pull llama3.2
python3 pacing_report.py manuscript.md --llm http://localhost:11434/v1 --model llama3.2
```

Any OpenAI-compatible endpoint works the same way. The tool only sends a short
excerpt (first and last ~600 characters) of each chapter, never your whole
manuscript. No API key is stored in any file — if `OPENAI_API_KEY` (or your
chosen env var) is unset, the request simply omits the `Authorization` header,
which is exactly what Ollama wants.

## What the flags mean

Flags are gentle observations, not verdicts:

- **long chapter / short chapter** — far above or below the book average
- **saggy middle candidate** — a middle chapter well over 1.5x average length
- **rushed ending candidate** — the final chapter is far below average
- **no scene breaks in a long chapter** — readers may want a breather
- **dialogue ratio low / very high** — narration-heavy or nearly all talk
- **slow opening / soft landing** — no strong first-page or pull-forward hook detected

Hook scores (0–3) note things like opening with dialogue, a question, quick
action, or a punchy short sentence — and closing on a question, a cliffhanger
image, or forward-leaning wording.

## Tests

```bash
python3 -m pytest test_pacing_report.py -v
```

## License

MIT — Copyright (c) 2026 Asdale Dynamics, LLC. See [LICENSE](LICENSE).
