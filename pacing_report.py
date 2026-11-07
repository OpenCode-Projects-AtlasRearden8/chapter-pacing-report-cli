#!/usr/bin/env python3
"""chapter-pacing-report-cli: per-chapter pacing checkup for markdown manuscripts.

Scans a markdown manuscript for chapter word counts, scene breaks,
dialogue-to-narration ratio, and opening/closing hooks, then prints a
per-chapter report with gentle pacing flags. Optional LLM summaries via any
OpenAI-compatible endpoint (including Ollama).

Part of the Asdale Dynamics author-tools collection.
Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict

__version__ = "1.0.0"

DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"

SCENE_BREAK_RE = re.compile(
    r"""^\s{0,3}(?:
        \*{3,}             # *** or *****
      | \*\s\*\s\*         # * * *
      | -{3,}              # ---
      | _{3,}              # ___
      | <hr\s*/?>          # <hr>
    )\s*$""",
    re.VERBOSE | re.IGNORECASE,
)

CHAPTER_TITLE_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")

QUOTE_RE = re.compile(r'"[^"]{2,}"|“[^”]{2,}”|‘[^’]{2,}’')

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")

WORD_RE = re.compile(r"\b[\w’'-]+\b")

HOOK_WORDS = re.compile(
    r"\b(never|finally|until|tomorrow|tonight|again|gone|dead|last|"
    r"before|behind|below|silence|blood|run|wait|why|who)\b",
    re.IGNORECASE,
)

ACTION_START_RE = re.compile(
    r"^\s*(ran|jumped|slammed|grabbed|threw|dashed|ducked|kicked|"
    r"shoved|burst|stumbled|spun|crashed|flew|hit| fired|bolted)",
    re.IGNORECASE,
)

CLIFFHANGER_RE = re.compile(
    r"(…|\.\.\.|--)$|"
    r"\b(only time would tell|had no idea|never come back|was gone|"
    r"too late|door (opened|closed|slammed)|phone rang|silence)\b",
    re.IGNORECASE,
)


@dataclass
class ChapterStats:
    number: int
    title: str
    word_count: int
    paragraph_count: int
    scene_breaks: int
    dialogue_words: int
    narration_words: int
    dialogue_ratio: float
    opening_score: int
    closing_score: int
    opening_notes: list[str] = field(default_factory=list)
    closing_notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def dialogue_word_count(text: str) -> int:
    total = 0
    for match in QUOTE_RE.finditer(text):
        total += count_words(match.group(0))
    return total


def sentences(text: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]


def score_opening(text: str) -> tuple[int, list[str]]:
    """Score the opening hook of a chapter body, 0-3, with friendly notes."""
    score = 0
    notes: list[str] = []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        return 0, ["chapter body is empty"]
    first = paras[0]
    first_sents = sentences(first)
    first_sent = first_sents[0] if first_sents else ""
    if first.lstrip().startswith(('"', "“", "‘")):
        score += 1
        notes.append("opens with dialogue")
    if "?" in first_sent:
        score += 1
        notes.append("opens with a question")
    if ACTION_START_RE.search(first_sent):
        score += 1
        notes.append("opens with immediate action")
    if first_sent and count_words(first_sent) <= 10:
        score += 1
        notes.append("short punchy opener")
    return score, notes


def score_closing(text: str) -> tuple[int, list[str]]:
    """Score the closing hook of a chapter body, 0-3, with friendly notes."""
    score = 0
    notes: list[str] = []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        return 0, ["chapter body is empty"]
    last = paras[-1]
    last_sents = sentences(last)
    last_sent = last_sents[-1] if last_sents else ""
    if last_sent.endswith("?"):
        score += 1
        notes.append("ends on a question")
    if CLIFFHANGER_RE.search(last_sent):
        score += 1
        notes.append("cliffhanger-style ending")
    if HOOK_WORDS.search(last_sent):
        score += 1
        notes.append("hooks with forward-pulling wording")
    if last_sent and count_words(last_sent) <= 10:
        score += 1
        notes.append("short punchy closer")
    return score, notes


def split_chapters(markdown: str, heading_level: int) -> list[tuple[str, str]]:
    """Split markdown into (title, body) chapters.

    Requires every chapter heading to use heading_level (e.g. '## Title' for
    level 2). Falls back to the first heading level found if none match.
    """
    level_pat = re.compile(rf"^\s{{0,3}}{'#' * heading_level}\s+(?!#)(.*)$")
    alt_laters = [
        re.compile(rf"^\s{{0,3}}{'#' * lvl}(?!#)\s+(.*)$")
        for lvl in range(1, heading_level)
    ]
    chapters: list[tuple[str, str]] = []
    current_title = None
    current_lines: list[str] = []
    found_target = False
    for line in markdown.splitlines():
        m = level_pat.match(line)
        if m:
            found_target = True
            if current_title is not None:
                chapters.append((current_title, "\n".join(current_lines)))
            current_title = m.group(1).strip()
            current_lines = []
            continue
        current_lines.append(line)
    if current_title is not None:
        chapters.append((current_title, "\n".join(current_lines)))
    if found_target and chapters:
        return chapters

    # Fallback: use first heading level that appears at all.
    markdown2 = markdown
    title = None
    chapters2: list[tuple[str, str]] = []
    lines_buf: list[str] = []
    any_heading = re.compile(r"^\s{0,3}#{1,6}\s+(?!#)(.*)$")
    for line in markdown2.splitlines():
        if any_heading.match(line):
            if title is not None:
                chapters2.append((title, "\n".join(lines_buf)))
            title = any_heading.match(line).group(1).strip()
            lines_buf = []
        else:
            lines_buf.append(line)
    if title is not None:
        chapters2.append((title, "\n".join(lines_buf)))
    return chapters2


def clean_body(body: str) -> str:
    """Drop markdown syntax that shouldn't count toward prose stats."""
    no_code = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    no_images = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", no_code)
    no_links = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", no_images)
    no_emph = re.sub(r"(\*\*?|__?)", " ", no_links)
    return no_emph


def parse_manuscript(markdown: str, heading_level: int = 2) -> list[ChapterStats]:
    chapters = split_chapters(markdown, heading_level)
    stats: list[ChapterStats] = []
    for idx, (title, raw_body) in enumerate(chapters, start=1):
        body = clean_body(raw_body)
        prose = re.sub(r"\n{2,}", "\n\n", body).strip()
        wc = count_words(prose)
        dwords = dialogue_word_count(prose)
        nwords = max(wc - dwords, 0)
        ratio = (dwords / wc) if wc else 0.0
        breaks = sum(1 for line in raw_body.splitlines() if SCENE_BREAK_RE.match(line))
        paras = [p for p in prose.split("\n\n") if p.strip()]
        open_score, open_notes = score_opening(prose)
        close_score, close_notes = score_closing(prose)
        stats.append(
            ChapterStats(
                number=idx,
                title=title or f"Chapter {idx}",
                word_count=wc,
                paragraph_count=len(paras),
                scene_breaks=breaks,
                dialogue_words=dwords,
                narration_words=nwords,
                dialogue_ratio=round(ratio, 3),
                opening_score=open_score,
                opening_notes=open_notes,
                closing_score=close_score,
                closing_notes=close_notes,
            )
        )
    return stats


def apply_flags(stats: list[ChapterStats]) -> None:
    """Add gentle, non-judgmental pacing flags based on book-level context."""
    if not stats:
        return
    counts = [c.word_count for c in stats if c.word_count > 0]
    mean = sum(counts) / len(counts) if counts else 0.0
    for c in stats:
        if mean > 0:
            deviation = (c.word_count - mean) / mean
            if deviation > 0.40:
                c.flags.append(
                    f"long chapter ({c.word_count} vs ~{int(mean)} avg) — "
                    "check for a saggy middle"
                )
            elif deviation < -0.40 and c.word_count < 300:
                c.flags.append("short chapter — verify pacing and content aren't rushed")
        if c.word_count > 3500 and c.scene_breaks == 0:
            c.flags.append(
                f"~{c.word_count} words with no scene breaks — readers may want a breather"
            )
        if c.dialogue_ratio < 0.12 and c.word_count > 200:
            c.flags.append(f"dialogue ratio {c.dialogue_ratio:.0%} is low — heavy narration")
        elif c.dialogue_ratio > 0.70 and c.word_count > 200:
            c.flags.append(f"dialogue ratio {c.dialogue_ratio:.0%} is very high — little narration")
        if c.opening_score == 0 and c.word_count > 200:
            c.flags.append("slow opening — consider a stronger first-page hook")
        if c.closing_score == 0 and c.word_count > 200:
            c.flags.append("soft landing — consider a pull-forward ending hook")

    # Book-level checks: saggy middle and rushed ending.
    if len(stats) >= 3 and mean > 0:
        middle = stats[1:-1]
        for c in middle:
            if c.word_count > mean * 1.5:
                c.flags.append(
                    f"saggy middle candidate — {c.word_count} words is well above the "
                    f"~{int(mean)} average"
                )
    last = stats[-1]
    first = stats[0]
    if mean > 0 and len(stats) >= 2:
        if last.word_count < mean * 0.55 and last.word_count < first.word_count * 0.55:
            last.flags.append(
                f"rushed ending candidate — final chapter ({last.word_count} words) is far "
                f"below the ~{int(mean)} average"
            )
        if last.word_count > 200 and last.closing_score == 0:
            last.flags.append("final chapter has no closing hook detected")


def fmt_report(stats: list[ChapterStats]) -> str:
    lines: list[str] = []
    total_words = sum(c.word_count for c in stats)
    total_breaks = sum(c.scene_breaks for c in stats)
    total_d = sum(c.dialogue_words for c in stats)
    overall_ratio = (total_d / total_words) if total_words else 0.0
    lines.append("Chapter Pacing Report")
    lines.append("=" * 60)
    lines.append(
        f"Chapters: {len(stats)}  |  Words: {total_words:,}  |  "
        f"Scene breaks: {total_breaks}  |  Dialogue: {overall_ratio:.0%}"
    )
    lines.append("")
    for c in stats:
        lines.append(f"Chapter {c.number}: {c.title}")
        lines.append(
            f"  Words: {c.word_count:,}  Paragraphs: {c.paragraph_count}  "
            f"Scene breaks: {c.scene_breaks}"
        )
        lines.append(
            f"  Dialogue: {c.dialogue_ratio:.0%} "
            f"({c.dialogue_words:,} of {c.word_count:,} words)"
        )
        open_txt = ", ".join(c.opening_notes) if c.opening_notes else "no strong hook detected"
        close_txt = ", ".join(c.closing_notes) if c.closing_notes else "no strong hook detected"
        lines.append(f"  Opening hook ({c.opening_score}/3): {open_txt}")
        lines.append(f"  Closing hook ({c.closing_score}/3): {close_txt}")
        if c.flags:
            lines.append("  Gentle flags:")
            for f in c.flags:
                lines.append(f"    - {f}")
        lines.append("")
    flagged = [c for c in stats if c.flags]
    lines.append(f"Chapters with flags: {len(flagged)} of {len(stats)}")
    return "\n".join(lines)


def llm_summaries(
    stats: list[ChapterStats], markdown: str, base_url: str, model: str,
    api_key_env: str, timeout: float,
) -> dict[int, str]:
    """Ask an OpenAI-compatible endpoint for a one-line pacing note per chapter.

    Works with Ollama (http://localhost:11434/v1) or any OpenAI-compatible
    server. Only short excerpts are sent. No API key is stored anywhere; the
    key is read from the environment variable named by api_key_env, and it's
    fine to run without one (Ollama doesn't need it).
    """
    chapters = split_chapters(markdown, 2)
    results: dict[int, str] = {}
    api_key = os.environ.get(api_key_env, "")
    url = base_url.rstrip("/") + "/chat/completions"
    for c in stats:
        body = ""
        if 0 < c.number <= len(chapters):
            body = chapters[c.number - 1][1]
        body = clean_body(body)
        excerpt = body[:600].strip() + " ... " + body[-600:].strip()
        prompt = (
            "You are a friendly pacing coach for authors. In one warm, "
            "encouraging sentence (max 40 words), note the pacing of this "
            "chapter excerpt: does it drag, rush, or flow well?\n\n"
            f"Chapter {c.number}: {c.title}\nWords: {c.word_count}\n\n{excerpt}"
        )
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 120,
                "temperature": 0.4,
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            content = data["choices"][0]["message"]["content"].strip()
            results[c.number] = " ".join(content.split())
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            results[c.number] = f"(LLM call failed: {exc.__class__.__name__}: {exc})"
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pacing_report",
        description=(
            "Chapter pacing checkup: word counts, scene breaks, "
            "dialogue ratio, hooks, and gentle pacing flags per chapter."
        ),
    )
    p.add_argument("manuscript", help="path to the markdown manuscript")
    p.add_argument(
        "--heading-level", type=int, choices=[1, 2, 3], default=2,
        help="heading level that marks a chapter (default: 2, i.e. '## Title')",
    )
    p.add_argument("--json", action="store_true", help="output JSON instead of a text report")
    p.add_argument("--llm", metavar="BASE_URL", default=None,
                   help="optional OpenAI-compatible endpoint base URL, e.g. http://localhost:11434/v1")
    p.add_argument("--model", default="llama3.2", help="model name for --llm (default: llama3.2)")
    p.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV,
                   help=f"env var holding the API key (default: {DEFAULT_API_KEY_ENV}; optional, Ollama needs none)")
    p.add_argument("--timeout", type=float, default=120.0, help="LLM HTTP timeout in seconds")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with open(args.manuscript, encoding="utf-8") as fh:
            markdown = fh.read()
    except OSError as exc:
        print(f"error: cannot read {args.manuscript}: {exc}", file=sys.stderr)
        return 2
    stats = parse_manuscript(markdown, args.heading_level)
    if not stats:
        print("error: no chapters found in manuscript", file=sys.stderr)
        return 1
    apply_flags(stats)
    if args.llm:
        summaries = llm_summaries(
            stats, markdown, args.llm, args.model, args.api_key_env, args.timeout
        )
        for c in stats:
            c.flags.append(f"LLM: {summaries.get(c.number, '(no summary)')}")
    if args.json:
        print(json.dumps([asdict(c) for c in stats], indent=2))
    else:
        print(fmt_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
