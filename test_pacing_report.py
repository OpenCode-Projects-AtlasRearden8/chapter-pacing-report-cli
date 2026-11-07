"""Tests for stats parsing in pacing_report.py."""

import json
import unittest

from pacing_report import (
    ChapterStats,
    apply_flags,
    count_words,
    dialogue_word_count,
    parse_manuscript,
    score_closing,
    score_opening,
    split_chapters,
)


class TestWordCount(unittest.TestCase):
    def test_basic_count(self):
        self.assertEqual(count_words("Hello world, hello dog."), 4)

    def test_empty(self):
        self.assertEqual(count_words(""), 0)

    def test_contractions(self):
        self.assertEqual(count_words("Don't stop—can't stop."), 4)

    def test_hyphenated(self):
        self.assertEqual(count_words("a well-known author"), 3)


class TestDialogue(unittest.TestCase):
    def test_simple_quotes(self):
        text = '"Hello there," she said. He walked home.'
        self.assertEqual(dialogue_word_count(text), 2)

    def test_curly_quotes(self):
        text = "“Get out,” he snapped. Then it was quiet."
        self.assertEqual(dialogue_word_count(text), 2)

    def test_no_dialogue(self):
        self.assertEqual(dialogue_word_count("Plain narration only."), 0)


class TestSplitChapters(unittest.TestCase):
    def test_level_two_headings(self):
        md = (
            "# Book\n\n"
            "## One\n\nAlpha text.\n\n"
            "## Two\n\nBeta text.\n"
        )
        chapters = split_chapters(md, 2)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0][0], "One")
        self.assertIn("Alpha text", chapters[0][1])
        self.assertEqual(chapters[1][0], "Two")

    def test_fallback_when_level_missing(self):
        md = "# Chapter A\n\nWords.\n\n# Chapter B\n\nMore.\n"
        chapters = split_chapters(md, 2)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0][0], "Chapter A")


class TestParseManuscript(unittest.TestCase):
    def make_md(self) -> str:
        return (
            "## The Storm\n\n"
            '"Get inside!" Maya shouted. The rain hammered the porch.\n\n'
            "They ran for the barn together. Did anyone check the windows?\n\n"
            "***\n\n"
            "Hours later, the clouds finally broke and a bird sang.\n\n"
            "## Quiet After\n\n"
            "Maya slept until noon. The afternoon passed in silence, page by "
            "page, drum by drum, note by note, without a single spoken word "
            "or interrupted thought until supper time came.\n"
        )

    def test_counts(self):
        stats = parse_manuscript(self.make_md(), 2)
        self.assertEqual(len(stats), 2)
        first = stats[0]
        self.assertEqual(first.title, "The Storm")
        self.assertEqual(first.scene_breaks, 1)
        self.assertGreater(first.dialogue_words, 0)
        self.assertGreater(first.dialogue_ratio, 0.0)
        self.assertEqual(first.dialogue_ratio, round(first.dialogue_ratio, 3))

    def test_code_blocks_excluded(self):
        md = "## One\n\n```python\nif x == 1:\n    print(x)\n```\n\nProse here.\n"
        stats = parse_manuscript(md, 2)
        # Code block words must not be counted.
        self.assertEqual(stats[0].word_count, count_words("Prose here."))

    def test_links_text_kept(self):
        md = "## One\n\nSee [the map](http://example.com) for details.\n"
        stats = parse_manuscript(md, 2)
        self.assertIn("map", stats[0].word_count and "the map for details")

    def test_all_stats_fields_populated(self):
        stats = parse_manuscript(self.make_md(), 2)
        for c in stats:
            self.assertIsInstance(c, ChapterStats)
            self.assertGreaterEqual(c.opening_score, 0)
            self.assertLessEqual(c.opening_score, 3)
            self.assertGreaterEqual(c.closing_score, 0)
            self.assertLessEqual(c.closing_score, 3)
            self.assertGreaterEqual(c.dialogue_ratio, 0.0)
            self.assertLessEqual(c.dialogue_ratio, 1.0)


class TestHooks(unittest.TestCase):
    def test_strong_open(self):
        score, notes = score_opening('"Who\'s there?" she whispered. "Answer me."')
        self.assertGreaterEqual(score, 2)
        self.assertIn("opens with dialogue", " ".join(notes))

    def test_weak_open(self):
        score, _ = score_opening(
            "The history of the region has been documented extensively by "
            "several notable scholars over many long and detailed decades "
            "of careful research."
        )
        self.assertEqual(score, 0)

    def test_cliffhanger_close(self):
        score, notes = score_closing("Then the phone rang...")
        self.assertGreaterEqual(score, 2)
        self.assertIn("cliffhanger-style ending", " ".join(notes))

    def test_question_close(self):
        score, notes = score_closing("But did she really leave?")
        self.assertGreaterEqual(score, 1)
        self.assertIn("ends on a question", " ".join(notes))

    def test_soft_close(self):
        score, _ = score_closing(
            "The meeting covered administrative details of the annual budget "
            "review process and adjourned at the usual scheduled hour."
        )
        self.assertEqual(score, 0)

    def test_empty_body(self):
        self.assertEqual(score_opening("")[0], 0)
        self.assertEqual(score_closing("")[0], 0)


class TestFlags(unittest.TestCase):
    def test_saggy_middle(self):
        stats = [
            ChapterStats(1, "A", 1000, 10, 1, 100, 900, 0.1, 2, 2),
            ChapterStats(2, "B", 4000, 40, 0, 100, 3900, 0.02, 2, 2),
            ChapterStats(3, "C", 1000, 10, 1, 100, 900, 0.1, 2, 2),
        ]
        apply_flags(stats)
        all_flags = " ".join(f for c in stats for f in c.flags)
        self.assertIn("saggy middle", all_flags)
        self.assertIn("heavy narration", all_flags)

    def test_rushed_ending(self):
        stats = [
            ChapterStats(1, "A", 2000, 20, 1, 400, 1600, 0.2, 2, 2),
            ChapterStats(2, "B", 2000, 20, 1, 400, 1600, 0.2, 2, 2),
            ChapterStats(3, "C", 500, 5, 0, 0, 500, 0.0, 2, 0),
        ]
        apply_flags(stats)
        self.assertTrue(
            any("rushed ending candidate" in f for f in stats[-1].flags)
        )
        self.assertTrue(any("no closing hook" in f for f in stats[-1].flags))

    def test_no_flags_for_healthy_book(self):
        stats = [
            ChapterStats(1, "A", 2000, 20, 2, 800, 1200, 0.4, 3, 3),
            ChapterStats(2, "B", 1900, 19, 2, 800, 1100, 0.42, 3, 3),
            ChapterStats(3, "C", 2000, 20, 2, 800, 1200, 0.4, 3, 3),
        ]
        apply_flags(stats)
        self.assertFalse(any(c.flags for c in stats))


class TestJsonOutput(unittest.TestCase):
    def test_stats_are_json_serializable(self):
        stats = parse_manuscript("## One\n\n\"Hi!\" he said.\n", 2)
        data = json.loads(json.dumps([vars(c) for c in stats]))
        self.assertEqual(data[0]["title"], "One")


if __name__ == "__main__":
    unittest.main()
