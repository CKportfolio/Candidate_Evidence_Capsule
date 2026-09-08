from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

# Unit tests should also be runnable in a lightweight development environment.
# The production dependency is installed by CI, but importing the module must not
# force a multi-hundred-megabyte model package onto someone who only wants to run
# the deterministic tests below.
if importlib.util.find_spec("sentence_transformers") is None:
    sentence_transformers_stub = types.ModuleType("sentence_transformers")

    class UnavailableSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError(
                "sentence-transformers is required for a real Story Mapper build"
            )

    sentence_transformers_stub.SentenceTransformer = UnavailableSentenceTransformer
    sys.modules["sentence_transformers"] = sentence_transformers_stub

import story_mapper as sm


class FakeSentenceTransformer:
    """Deterministic embedding stand-in; no model download or network access."""

    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, texts, normalize_embeddings=True, **_kwargs):
        rows = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big")
            row = np.random.default_rng(seed).normal(size=384).astype(np.float32)
            if normalize_embeddings:
                row /= np.linalg.norm(row)
            rows.append(row)
        return np.vstack(rows)


class TextProcessingTests(unittest.TestCase):
    def test_read_text_supports_utf8_and_cp1250(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            utf8 = root / "utf8.txt"
            cp1250 = root / "cp1250.txt"
            utf8.write_text("Zażółć gęślą jaźń", encoding="utf-8")
            cp1250.write_bytes("Zażółć gęślą jaźń".encode("cp1250"))

            self.assertEqual(sm.read_text(utf8), "Zażółć gęślą jaźń")
            self.assertEqual(sm.read_text(cp1250), "Zażółć gęślą jaźń")

    def test_clean_removes_markup_and_code_blocks(self):
        source = """# Nagłówek

- [Projekt](https://example.com)

```python
secret = 'not narrative'
```

<b>Końcowy tekst</b>
"""
        cleaned = sm.clean(source)

        self.assertIn("Nagłówek", cleaned)
        self.assertIn("Projekt", cleaned)
        self.assertIn("Końcowy tekst", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("secret", cleaned)
        self.assertNotIn("<b>", cleaned)

    def test_split_atoms_deduplicates_case_insensitively(self):
        text = (
            "To jest wystarczająco długi, samodzielny fragment historii projektu.\n\n"
            "TO JEST WYSTARCZAJĄCO DŁUGI, SAMODZIELNY FRAGMENT HISTORII PROJEKTU."
        )

        self.assertEqual(
            sm.split_atoms(text),
            ["To jest wystarczająco długi, samodzielny fragment historii projektu."],
        )


class StableIdentityTests(unittest.TestCase):
    def test_known_namespaces_are_stable(self):
        self.assertEqual(
            sm.stable_extra_prefix(Path("historia candidate capsule.txt")),
            "EX6",
        )
        self.assertEqual(sm.stable_repo_slot("BOT_EU"), "1")
        self.assertEqual(sm.stable_repo_slot("story_mapper"), "10")

    def test_unknown_namespaces_are_deterministic(self):
        first = sm.stable_extra_prefix(Path("Nowa historia.txt"))
        second = sm.stable_extra_prefix(Path("nowa historia.txt"))
        self.assertEqual(first, second)
        self.assertRegex(first, r"^EXX[0-9A-F]{8}-$")

    def test_project_is_resolved_from_nested_repo_path(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            input_dir = root / "input"
            nested = input_dir / "repo" / "MAG-AS" / "docs" / "architecture.md"
            with patch.object(sm, "INPUT", input_dir):
                self.assertEqual(sm.repo_project_from_path(nested), "MAG-AS")

        self.assertEqual(
            sm.project_name("input/repo/MAG-AS/docs/architecture.md"),
            "MAG-AS",
        )

    def test_repo_url_uses_public_github_organization(self):
        self.assertEqual(
            sm.repo_url_for_project("MAG-AS"),
            "https://github.com/CKportfolio/MAG-AS",
        )


class SemanticHelpersTests(unittest.TestCase):
    def test_normalize_handles_zero_and_unit_length(self):
        zero = np.zeros(3, dtype=np.float32)
        np.testing.assert_array_equal(sm.normalize(zero), zero)
        self.assertAlmostEqual(float(np.linalg.norm(sm.normalize([3.0, 4.0]))), 1.0)

    def test_leave_one_source_out_small_corpus_is_explicit(self):
        result = sm.leave_one_source_out(
            {
                "one": np.array([1.0, 0.0], dtype=np.float32),
                "two": np.array([0.0, 1.0], dtype=np.float32),
            }
        )
        self.assertEqual(result, {"mean": 1.0, "min": 1.0, "by_source": {}})

    def test_evidence_index_does_not_replace_missing_source_ids(self):
        narrative = [sm.Atom("LM0017", "LM", "input/LM_LONG.txt", "Human role")]
        cv_atoms = [sm.Atom("CV10001", "CV", "input/CV.pdf", "AI-assisted")]
        topics = sm.build_evidence_index(narrative, [], cv_atoms)
        first_topic_ids = [item["id"] for item in topics[0]["entries"]]

        self.assertEqual(first_topic_ids, ["CV10001", "LM0017"])
        self.assertNotIn("CV10003", first_topic_ids)


class RepositoryContractTests(unittest.TestCase):
    def test_source_and_readme_match_current_non_prompt_version(self):
        root = Path(sm.__file__).resolve().parent
        source = (root / "story_mapper.py").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        combined = source + "\n" + readme

        self.assertIn("6.0.0-non-prompt-public-page", source)
        self.assertNotIn("TARGET_JOB_URL", combined)
        self.assertNotIn("PROJECT_VERIFICATION_SPECS", combined)
        self.assertNotIn("Artifact Evidence Quality Engine", combined)
        self.assertNotIn("evidences.stronazen.pl", combined)
        self.assertNotIn("drive.google.com", combined)
        self.assertNotIn("/UNKNOWN/", combined)


class IntegrationBuildTests(unittest.TestCase):
    def test_main_builds_all_outputs_without_downloading_model(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            input_dir = root / "input"
            output_dir = root / "output"
            extra_dir = input_dir / "extra"
            repo_dir = input_dir / "repo" / "BOT_EU"
            docs_dir = repo_dir / "docs"
            extra_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            narrative = [
                (
                    f"Historia numer {number} opisuje konkretny problem operacyjny, "
                    "decyzję projektową, eksperyment oraz wynik wdrożenia."
                )
                for number in range(1, 31)
            ]
            (input_dir / "LM_LONG.txt").write_text(
                "\n\n".join(narrative),
                encoding="utf-8",
            )
            (extra_dir / sm.ORIGIN_STORY_FILENAME).write_text(
                "Ta publiczna strona powstała przez testy oraz świadome upraszczanie architektury.",
                encoding="utf-8",
            )

            repo_atoms = [
                (
                    f"Komponent {number} projektu BOT_EU opisuje testy, obsługę błędów, "
                    "integrację API oraz decyzję architektoniczną."
                )
                for number in range(1, 13)
            ]
            (repo_dir / "README.md").write_text(
                "\n\n".join(repo_atoms),
                encoding="utf-8",
            )
            (docs_dir / "architecture.md").write_text(
                "Dodatkowa dokumentacja opisuje granice modułów oraz przepływ danych w aplikacji.",
                encoding="utf-8",
            )

            with (
                patch.object(sm, "ROOT", root),
                patch.object(sm, "INPUT", input_dir),
                patch.object(sm, "OUTPUT", output_dir),
                patch.object(sm, "SentenceTransformer", FakeSentenceTransformer),
            ):
                sm.main()

            markdown_path = output_dir / "CEZARY_KRYCH.semantic.md"
            json_path = output_dir / "CEZARY_KRYCH.semantic.json"
            raw_path = output_dir / "CEZARY_KRYCH.raw_sources.md"

            self.assertTrue(markdown_path.is_file())
            self.assertTrue(json_path.is_file())
            self.assertTrue(raw_path.is_file())

            page = markdown_path.read_text(encoding="utf-8")
            data = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertIn("PUBLIC CANDIDATE KNOWLEDGE PAGE", page)
            self.assertIn("Ta publiczna strona powstała", page)
            self.assertIn("https://github.com/CKportfolio/BOT_EU", page)
            self.assertEqual(page.count("## BOT_EU"), 1)
            self.assertNotIn("PROJECT_SPECIFIC_VERIFICATION", page)
            self.assertNotIn("POSSIBLE_VERIFICATION", page)
            self.assertNotIn("evidences.stronazen.pl", page)

            self.assertEqual(
                data["page_schema_version"],
                "6.0.0-non-prompt-public-page",
            )
            self.assertFalse(data["contains_llm_evaluation_instructions"])
            self.assertFalse(data["contains_llm_interaction_instructions"])
            self.assertEqual(len(data["project_cards"]), 1)
            self.assertEqual(data["project_cards"][0]["project"], "BOT_EU")
            self.assertEqual(len(data["project_cards"][0]["sources"]), 2)

            registry_ids = re.findall(r"^## \[([^]]+)]$", page, flags=re.MULTILINE)
            self.assertEqual(len(registry_ids), len(set(registry_ids)))


if __name__ == "__main__":
    unittest.main()
