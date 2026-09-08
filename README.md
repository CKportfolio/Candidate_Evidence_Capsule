# story_mapper — Candidate Knowledge Page Generator

[![CI](https://github.com/CKportfolio/story_mapper/actions/workflows/ci.yml/badge.svg)](https://github.com/CKportfolio/story_mapper/actions/workflows/ci.yml)

`story_mapper.py` builds a public, machine-readable candidate knowledge page from several kinds of source material: a professional narrative, a CV, project documentation and additional project histories.

The project grew out of a simple limitation of conventional recruitment documents. A short CV can present dates, roles and technologies, but it has little room for the reasoning behind projects: where a problem came from, how it was decomposed, what changed during implementation and why a solution was simplified or stopped.

The generator keeps that richer context in one structured source suitable for publication as a portfolio subpage. The page remains readable by a person, while its stable identifiers, provenance labels, retrieval index and JSON summary make navigation easier for software and AI systems.

## Design principles

### Knowledge, not a conversational script

The generated page contains no recruiter question templates, model directives, prescribed assessment procedure or hiring conclusion. It describes the candidate and maps the supplied sources without telling the reader what opinion to form.

### Explicit provenance

Each text atom is marked according to its origin:

- `STORY-CLAIM` — candidate narrative or an additional history;
- `CV-DECLARED` — information extracted from the CV;
- `REPO-DOCUMENTED` — information contained in candidate-authored repository documentation;
- `DERIVED-SIGNAL` — a relationship or ordering produced by semantic/statistical analysis;
- `INFERENCE` — an interpretation built from several data points;
- `UNKNOWN` — the supplied material does not determine the matter.

These labels preserve the distinction between what a source says and what might be established by an independent code or runtime audit.

### Stable source identifiers

Known stories and repositories use permanent namespaces. Adding a new file does not silently renumber the source IDs already referenced by the curated index. Unknown sources receive deterministic namespaces derived from their names.

### Precision before automatic guessing

The Evidence Index uses manually reviewed, source-locked atom IDs. If a referenced atom disappears, the generator omits that entry rather than silently replacing it with a semantically similar passage.

### Semantic analysis without semantic judgment

The generator uses `intfloat/multilingual-e5-small` to create normalized embeddings. They support:

- source-balanced narrative representation;
- central story fragments;
- exploratory semantic groupings;
- relationships between narrative themes and project documentation;
- leave-one-story-out sensitivity diagnostics.

These results organize meaning within the supplied corpus. They are not truth probabilities, candidate scores or competency ratings.

## Input layout

```text
story_mapper/
├── story_mapper.py
├── requirements.txt
├── input/
│   ├── LM_LONG.txt
│   ├── candidate_cv.pdf
│   ├── extra/
│   │   ├── historia pierwszych automatyzacji.txt
│   │   ├── ml bot history.txt
│   │   ├── program do wprowadzania zlecen.txt
│   │   ├── plyciarz history.txt
│   │   └── historia candidate capsule.txt
│   └── repo/
│       ├── BOT_EU/README.md
│       ├── Demand-Radar/README.md
│       ├── MAG-AS/README.md
│       ├── PiTcA/README.md
│       ├── StreszCzarka---Krypto-AI-news-serwis/README.md
│       ├── Zonda-Kalkulator-PITolenia-/README.md
│       ├── market-data-intelligence-lab/README.md
│       ├── web-3Dviever-glb/README.md
│       ├── wynajem_motorowek/README.md
│       └── story_mapper/README.md
├── tests/
│   └── test_story_mapper.py
└── .github/
    └── workflows/ci.yml
```

`LM_LONG.txt` is required. PDF files in the input root are treated as CV sources. Markdown and text files inside `input/extra` become narrative sources. Markdown and text files under each `input/repo/<project>/` directory become project-documentation sources; a project README is loaded first.

The origin story has a stable filename:

```text
input/extra/historia candidate capsule.txt
```

Its full text is shown in the opening section of the generated page and is also atomized into the Evidence Registry.

## Requirements

- Python 3.10 or newer;
- `numpy`;
- `pypdf`;
- `sentence-transformers`;
- `scikit-learn`.

Example environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy pypdf sentence-transformers scikit-learn
```

The embedding model is downloaded on first use, so the first build may take longer than subsequent runs.

## Build

Run the generator from the project directory:

```bash
python story_mapper.py
```

Generated artifacts are written to `output/`:

```text
output/
├── CEZARY_KRYCH.semantic.md
├── CEZARY_KRYCH.semantic.json
└── CEZARY_KRYCH.raw_sources.md
```

- `CEZARY_KRYCH.semantic.md` is the complete source for the public knowledge page;
- `CEZARY_KRYCH.semantic.json` contains the machine-readable summary;
- `CEZARY_KRYCH.raw_sources.md` is a build companion containing the unprocessed narrative inputs.

The Markdown source can be converted to a static portfolio page with the separate `story_mapper_site.py` renderer:

```bash
python story_mapper_site.py \
  --input output/CEZARY_KRYCH.semantic.md \
  --output candidate/index.html \
  --base-url https://example.com/candidate/
```

The public domain is intentionally not hardcoded in the generator.
The renderer is maintained separately and is not included in this repository.

## Tests and CI

The test suite uses Python's standard `unittest` module and does not download the embedding model. A deterministic local stand-in is used in the integration test, so the pipeline checks the complete build path without depending on an external model service.

Run the same checks locally:

```bash
python -m py_compile story_mapper.py
python -m unittest discover -s tests -v
```

GitHub Actions runs these checks automatically on every push to `main` and for every pull request. The workflow also installs the declared dependencies and runs `pip check`.

## Generated page structure

The result contains:

1. origin and evolution of the project;
2. provenance vocabulary and truth-layer definitions;
3. source-locked Evidence Index;
4. compact Claim Graph;
5. project cards with direct GitHub repository links;
6. semantic relationships and exploratory groupings;
7. canonical Evidence Registry;
8. methodology and a machine-readable JSON summary.

Project links point directly to the public repositories in the [`CKportfolio` GitHub organization](https://github.com/orgs/CKportfolio/repositories).

## What the project does not do

The generator does not execute project code, measure runtime behavior, establish authorship independently or perform a security audit. Repository README files remain candidate-authored documentation. The output is a structured portfolio source, not an independent certification.

The semantic pipeline also does not decide whether the candidate should be hired or assign a software-engineering level. Those judgments remain outside the generator.

## Privacy and publication

Everything placed in `input/` may be reproduced or represented in generated output. Private contact details, credentials, API keys and confidential client data should therefore be removed before building a public page.

The generator itself can be public while private source variants remain outside the repository. A clean example corpus or redacted input set is preferable for demonstrations.

## Project evolution

Earlier versions experimented with large prompts, recruiter question sets, static repository mirrors and detailed fallback procedures for models that could not open links embedded in attachments. Tests across several AI providers showed that adding more instructions created complexity without reliably changing tool-access policies.

The current design solves that problem at the delivery layer. The knowledge base is published as a normal portfolio subpage reachable through one direct URL, while project code stays in ordinary public GitHub repositories. The result is smaller, provider-neutral and intentionally non-prompt.

## Status

This is an experimental portfolio and information-architecture project developed through repeated implementation, red-team testing, cross-provider trials and simplification. Its main subject is not automated candidate scoring, but the faithful organization of a complex professional story.
