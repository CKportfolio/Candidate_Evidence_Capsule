from __future__ import annotations

import json
import hashlib
import math
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
MODEL_NAME = "intfloat/multilingual-e5-small"
TEXT_EXT = {".txt", ".md", ".markdown"}
CANDIDATE_NAME = "Cezary Krych"
GITHUB_ORG = "CKportfolio"
PAGE_SOURCE = "CEZARY_KRYCH.semantic.md"
GENERATOR_VERSION = "6.0.0-non-prompt-public-page"
ORIGIN_STORY_FILENAME = "historia candidate capsule.txt"

# Permanent source namespaces.  Adding a new story or repository must not
# silently renumber the source IDs already used by the curated Evidence Index.
EXTRA_SOURCE_SLOTS = {
    "historia pierwszych automatyzacji.txt": "EX2",
    "ml bot history.txt": "EX3",
    "program do wprowadzania zlecen.txt": "EX4",
    "plyciarz history.txt": "EX5",
    "historia candidate capsule.txt": "EX6",
}

REPO_SOURCE_SLOTS = {
    "BOT_EU": "1",
    "Demand-Radar": "2",
    "MAG-AS": "3",
    "PiTcA": "4",
    "StreszCzarka---Krypto-AI-news-serwis": "5",
    "Zonda-Kalkulator-PITolenia-": "6",
    "market-data-intelligence-lab": "7",
    "web-3Dviever-glb": "8",
    "wynajem_motorowek": "9",
    "story_mapper": "10",
}


@dataclass
class Atom:
    id: str
    kind: str
    source: str
    text: str


def read_text(path: Path) -> str:
    b = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1250", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def ascii_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def stable_extra_prefix(path: Path) -> str:
    key = ascii_key(path.name)
    known = {ascii_key(name): prefix for name, prefix in EXTRA_SOURCE_SLOTS.items()}
    if key in known:
        return known[key]
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()
    return f"EXX{digest}-"


def repo_project_from_path(path: Path) -> str:
    """Resolve input/repo/<PROJECT>/... without depending on file order."""
    try:
        relative = path.relative_to(INPUT / "repo")
    except ValueError:
        return path.parent.name
    return relative.parts[0] if len(relative.parts) > 1 else path.stem


def stable_repo_slot(project: str) -> str:
    if project in REPO_SOURCE_SLOTS:
        return REPO_SOURCE_SLOTS[project]
    digest = hashlib.sha1(ascii_key(project).encode("utf-8")).hexdigest()[:8].upper()
    return f"X{digest}-"


def repo_file_rank(path: Path) -> tuple[int, str]:
    name = path.name.casefold()
    if name == "readme.md":
        return (0, str(path).casefold())
    if name in {"readme.markdown", "readme.txt"}:
        return (1, str(path).casefold())
    return (2, str(path).casefold())


def clean(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+•]\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


def split_atoms(text: str, min_chars=30, max_chars=520):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n{2,}|\n(?=\s*[-•*])", text)
    out, seen = [], set()

    def push(x):
        x = re.sub(r"^\s*[-•*]\s*", "", x.strip())
        x = re.sub(r"\s+", " ", x)
        if len(x) < min_chars or x.lower() in seen:
            return
        seen.add(x.lower())
        out.append(x)

    for part in parts:
        if not part.strip():
            continue
        sents = re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"'])", part.strip())
        for s in sents:
            if len(s) <= max_chars:
                push(s)
            else:
                for c in re.split(r"\s*[;]\s*|\s+—\s+|\s+-\s+(?=[a-ząćęłńóśźż])", s):
                    if len(c) <= max_chars:
                        push(c)
                    else:
                        for i in range(0, len(c), max_chars):
                            push(c[i:i + max_chars])
    return out


def load_text_file(path: Path, kind: str, prefix: str):
    return [Atom(f"{prefix}{i:04d}", kind, str(path.relative_to(ROOT)), t)
            for i, t in enumerate(split_atoms(clean(read_text(path))), 1)]


def load_pdf_file(path: Path, kind: str, prefix: str):
    return [Atom(f"{prefix}{i:04d}", kind, str(path.relative_to(ROOT)), t)
            for i, t in enumerate(split_atoms(read_pdf(path)), 1)]


def encode(model, atoms):
    if not atoms:
        return np.zeros((0, 384), dtype=np.float32)
    return np.asarray(model.encode(
        ["passage: " + a.text for a in atoms],
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=32,
    ), dtype=np.float32)


def normalize(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v if n == 0 else v / n


def centroid(mat):
    return None if len(mat) == 0 else normalize(np.mean(mat, axis=0))


def groups_by_source(atoms):
    g = defaultdict(list)
    for i, a in enumerate(atoms):
        g[a.source].append(i)
    return g


def robust_source_vectors(atoms, emb, keep_fraction=.72):
    out = {}
    for source, inds in groups_by_source(atoms).items():
        c0 = centroid(emb[inds])
        sims = emb[inds] @ c0
        keep_n = max(2, int(math.ceil(len(inds) * keep_fraction)))
        order = np.argsort(sims)[::-1]
        kept = [inds[j] for j in order[:keep_n]]
        out[source] = centroid(emb[kept])
    return out


def leave_one_source_out(source_vectors):
    names = list(source_vectors)
    if len(names) < 3:
        return {"mean": 1.0, "min": 1.0, "by_source": {}}
    full = centroid(np.vstack([source_vectors[n] for n in names]))
    vals = {}
    for dropped in names:
        loo = centroid(np.vstack([source_vectors[n] for n in names if n != dropped]))
        vals[dropped] = float(np.dot(full, loo))
    return {"mean": float(np.mean(list(vals.values()))),
            "min": float(np.min(list(vals.values()))),
            "by_source": vals}


def cross_story_consensus(atom_vec, source_vectors, own_source):
    vals = [float(np.dot(atom_vec, vec)) for src, vec in source_vectors.items() if src != own_source]
    return float(np.median(vals)) if vals else 0.0


def residualize(emb, fingerprint):
    proj = emb @ fingerprint
    res = emb - proj[:, None] * fingerprint[None, :]
    norms = np.linalg.norm(res, axis=1, keepdims=True)
    norms[norms < 1e-8] = 1.0
    return (res / norms).astype(np.float32)


def choose_k(res):
    n = len(res)
    if n < 8:
        return max(2, min(3, n - 1)), {}
    max_k = min(8, max(4, int(math.sqrt(n)) + 1), n - 1)
    best_k, best_adj, scores = 3, -999.0, {}
    for k in range(3, max_k + 1):
        labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(res)
        counts = np.bincount(labels)
        singletons = int(np.sum(counts == 1))
        sil = float(silhouette_score(res, labels, metric="cosine"))
        adj = sil - 0.015 * singletons
        scores[k] = {"silhouette": sil, "singletons": singletons, "adjusted": adj}
        if adj > best_adj:
            best_k, best_adj = k, adj
    return best_k, scores


def build_themes(narrative, emb, fingerprint):
    res = residualize(emb, fingerprint)
    k, k_scores = choose_k(res)
    labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(res)
    themes = []
    for lab in sorted(set(labels)):
        inds = np.where(labels == lab)[0].tolist()
        rc = centroid(res[inds])
        oc = centroid(emb[inds])
        sims = res[inds] @ rc
        reps = [inds[j] for j in np.argsort(sims)[::-1][:min(5, len(inds))]]
        themes.append({"label": int(lab), "inds": inds, "size": len(inds),
                       "original_centroid": oc, "reps": reps})
    themes.sort(key=lambda t: t["size"], reverse=True)
    return labels, themes, k_scores


def project_name(source):
    p = Path(source)
    parts = p.parts
    if "repo" in parts:
        repo_index = parts.index("repo")
        if repo_index + 1 < len(parts):
            return parts[repo_index + 1]
    return p.parent.name or p.stem


def theme_evidence(theme, evidence, e_emb, repo_vectors):
    matches = sorted(
        [(src, float(np.dot(theme["original_centroid"], vec))) for src, vec in repo_vectors.items()],
        key=lambda x: x[1], reverse=True
    )
    out = []
    for source, source_score in matches[:3]:
        inds = [i for i, a in enumerate(evidence) if a.source == source]
        if not inds:
            continue
        sims = e_emb[inds] @ theme["original_centroid"]
        j = inds[int(np.argmax(sims))]
        out.append({"project": project_name(source), "source": source,
                    "source_score": source_score, "atom_id": evidence[j].id,
                    "text": evidence[j].text})
    return out


def repo_evidence_bank(evidence, e_emb, theme_centroids, per_repo=6):
    bank = {}
    project_groups = defaultdict(list)
    for index, atom in enumerate(evidence):
        project_groups[project_name(atom.source)].append(index)

    for project, inds in project_groups.items():
        local = e_emb[inds]
        rc = centroid(local)
        central = np.argsort(local @ rc)[::-1]
        if theme_centroids:
            tmat = np.vstack(theme_centroids)
            thematic = np.argsort(np.max(local @ tmat.T, axis=1))[::-1]
        else:
            thematic = central
        chosen = []
        for order, limit in ((central, 2), (thematic, 4)):
            for li in order:
                gi = inds[int(li)]
                if gi not in chosen:
                    chosen.append(gi)
                if len(chosen) >= limit:
                    break
        for li in range(len(inds)):
            gi = inds[li]
            if gi not in chosen:
                chosen.append(gi)
            if len(chosen) >= per_repo:
                break
        bank[project] = chosen[:per_repo]
    return bank


def max_sim(vec, mat):
    return float(np.max(mat @ vec)) if len(mat) else 0.0


def add_atom(lines, atom):
    lines.append(f"- **[{atom.id}]** `{atom.kind}` `{atom.source}` — {atom.text}")




# ============================================================
# V5.5 — SOURCE-LOCKED EVIDENCE INDEX
#
# Precision > recall.
#
# No lexical stemming, substring matching, embedding rematching
# or fallback search is used for Evidence Index membership.
#
# Each topic points only to manually reviewed atom IDs.
# Missing IDs are omitted rather than replaced with "similar" text.
#
# The index is a retrieval map, not an evidence-strength model.
# ============================================================

EVIDENCE_INDEX_SPECS = [
    {
        "topic": "AI_ASSISTED_ROLE_AND_HUMAN_CONTRIBUTION",
        "aliases": [
            "AI-assisted development",
            "candidate vs AI",
            "human contribution",
            "what did the candidate do",
        ],
        "source_ids": [
            "CV10001", "CV10003", "CV10038", "CV10039",
            "EX20011", "LM0017",
        ],
    },
    {
        "topic": "SOFTWARE_TESTING_AND_CI",
        "aliases": [
            "tests", "testing", "CI", "GitHub Actions",
            "regression tests", "verification boundaries",
        ],
        "source_ids": [
            "RP40024", "RP40025", "RP40026",
            "RP50015", "RP50016",
            "RP70038", "RP70039",
            "CV10032",
        ],
    },
    {
        "topic": "SECURITY",
        "aliases": [
            "security", "credentials", "allowlist",
            "CodeQL", "secrets", "network safety",
        ],
        "source_ids": [
            "RP50015", "CV10026", "CV10032",
        ],
    },
    {
        "topic": "AUTOMATION_AND_PROCESS_MAPPING",
        "aliases": [
            "automation", "business process automation",
            "manual process", "workflow", "process mapping",
        ],
        "source_ids": [
            "EX20005", "EX20009", "EX20011", "EX20013",
            "EX20014", "EX40011", "EX50011", "RP40022",
        ],
    },
    {
        "topic": "BUSINESS_REQUIREMENTS_AND_REAL_USERS",
        "aliases": [
            "business requirements", "real user problem",
            "client need", "business value", "nontechnical user",
        ],
        "source_ids": [
            "EX20001", "EX20011", "EX20014",
            "RP40020", "RP40022",
            "CV10003", "CV10005", "CV10034",
        ],
    },
    {
        "topic": "API_AND_EXTERNAL_INTEGRATIONS",
        "aliases": [
            "API", "external integrations", "Zoom API",
            "Bybit API", "Supabase", "Apify",
        ],
        "source_ids": [
            "EX20009", "EX20013", "RP10016", "RP50004",
            "CV10013", "CV10016", "CV10036",
        ],
    },
    {
        "topic": "ML_EXPERIMENTATION_AND_TIME_SERIES_VALIDATION",
        "aliases": [
            "ML", "machine learning", "time series", "walk-forward",
            "embargo", "leakage", "holdout",
        ],
        "source_ids": [
            "RP70029", "RP70030", "RP70031", "RP70032",
            "RP70033", "RP70034", "RP70035", "RP70037",
            "CV10018",
        ],
    },
    {
        "topic": "DATA_PIPELINES_AND_TRANSFORMATION",
        "aliases": [
            "data pipeline", "CSV transformation", "normalization",
            "OCR", "deduplication", "data engineering",
        ],
        "source_ids": [
            "RP40007", "RP40008",
            "RP50001", "RP50002", "RP50003",
            "EX40011", "EX50011", "CV10016",
        ],
    },
    {
        "topic": "DEPLOYMENT_HOSTING_AND_RUNTIME",
        "aliases": [
            "deployment", "hosting", "VPS", "Docker",
            "Render", "GitHub Pages", "runtime",
        ],
        "source_ids": [
            "EX20007", "RP50004",
            "RP80008", "RP80009", "RP80011",
            "CV10016", "CV10036",
        ],
    },
    {
        "topic": "PRODUCTION_STATUS_SCALE_AND_LIMITATIONS",
        "aliases": [
            "production", "prototype", "pre-production",
            "utility project", "scale", "limitations",
        ],
        "source_ids": [
            "RP40022", "RP90019", "RP90016", "RP10032",
        ],
    },
    {
        "topic": "ERROR_HANDLING_DEBUGGING_AND_EDGE_CASES",
        "aliases": [
            "debugging", "edge cases", "error handling",
            "recovery", "restart", "regression bug", "race condition",
        ],
        "source_ids": [
            "RP10014",
            "RP70038", "RP70039",
            "RP90003", "RP90006", "RP90020",
        ],
    },
    {
        "topic": "ITERATION_SIMPLIFICATION_AND_OVERENGINEERING",
        "aliases": [
            "iteration", "simplification", "overengineering",
            "complexity", "changed direction", "experimental decision",
        ],
        "source_ids": [
            "EX30002",
            "RP70031", "RP70032", "RP70033", "RP70034",
            "CV10030",
        ],
    },
    {
        "topic": "TEAM_OPERATIONS_AND_NONTECHNICAL_USERS",
        "aliases": [
            "teamwork", "operations", "people coordination",
            "nontechnical users", "change adoption",
        ],
        "source_ids": [
            "LM0008", "LM0017",
            "CV10009", "CV10033", "CV10034",
        ],
    },
    {
        "topic": "DOCUMENTATION_MAINTENANCE_AND_HANDOFF",
        "aliases": [
            "technical documentation", "maintenance",
            "handoff", "project hardening", "takeover readiness",
        ],
        "source_ids": [
            "CV10026", "CV10032",
        ],
    },
]


def _retrieval_preview(s, limit=170):
    compact = " ".join(s.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit - 1].rstrip() + "…"


def build_evidence_index(narrative, evidence, cv_atoms):
    """
    Source-locked retrieval map.

    No lexical search.
    No semantic search.
    No substring/stem matching.
    No fallback.

    Every index entry is emitted only when its reviewed atom ID
    exists in the current page source corpus.

    The index says WHERE relevant source material is located.
    It does not say HOW STRONG that evidence is.
    """
    all_atoms = narrative + evidence + cv_atoms
    atom_map = {a.id: a for a in all_atoms}
    topics = []

    for spec in EVIDENCE_INDEX_SPECS:
        entries = []

        for display_rank, sid in enumerate(spec["source_ids"], 1):
            atom = atom_map.get(sid)
            if atom is None:
                continue

            entries.append({
                "retrieval_rank": display_rank,
                "id": atom.id,
                "kind": atom.kind,
                "source": atom.source,
                "project": (
                    project_name(atom.source)
                    if atom.kind == "REPO"
                    else None
                ),
                "preview": _retrieval_preview(atom.text),
                "selection_method": "SOURCE_LOCKED_CURATED_ID",
            })

        topics.append({
            "topic": spec["topic"],
            "aliases": spec["aliases"],
            "entries": entries,
            "selection_method": "SOURCE_LOCKED_CURATED_IDS",
        })

    return topics


def repo_url_for_project(project):
    return f"https://github.com/{GITHUB_ORG}/{project}"

def main():
    OUTPUT.mkdir(exist_ok=True)
    lm_path = INPUT / "LM_LONG.txt"
    if not lm_path.exists():
        print("[BLAD] Brakuje input/LM_LONG.txt")
        sys.exit(2)

    # SOURCE ROLES -------------------------------------------------
    # Identity/story: LM_LONG + EXTRA
    # Project documentation: README
    # Formal representation: CV
    narrative = load_text_file(lm_path, "LM", "LM")
    extra_paths = []
    extra = INPUT / "extra"
    if extra.exists():
        for p in sorted(extra.rglob("*"), key=lambda item: ascii_key(str(item))):
            if p.is_file() and p.suffix.lower() in TEXT_EXT and p.name.lower() != "readme.txt":
                extra_paths.append(p)
                narrative += load_text_file(p, "EXTRA", stable_extra_prefix(p))

    origin_story_path = next(
        (p for p in extra_paths if ascii_key(p.name) == ascii_key(ORIGIN_STORY_FILENAME)),
        None,
    )
    origin_story_text = (
        read_text(origin_story_path).strip()
        if origin_story_path
        else (
            "Ta strona powstała jako rozszerzenie klasycznego CV: publiczna, "
            "ustrukturyzowana baza wiedzy łącząca historię zawodową, projekty "
            "i ich źródła. Pełna historia projektu może zostać dodana jako "
            f"`input/extra/{ORIGIN_STORY_FILENAME}`."
        )
    )

    evidence = []
    repo = INPUT / "repo"
    if repo.exists():
        repo_files = [p for p in repo.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXT and p.name.lower() != "readme.txt"]
        repo_groups = defaultdict(list)
        for p in repo_files:
            repo_groups[repo_project_from_path(p)].append(p)
        for project in sorted(repo_groups, key=ascii_key):
            slot = stable_repo_slot(project)
            for file_number, p in enumerate(sorted(repo_groups[project], key=repo_file_rank), 1):
                prefix = f"RP{slot}" if file_number == 1 else f"RP{slot}F{file_number}-"
                evidence += load_text_file(p, "REPO", prefix)

    cv_paths = sorted(INPUT.glob("*.pdf"))
    cv_atoms = []
    for idx, p in enumerate(cv_paths, 1):
        cv_atoms += load_pdf_file(p, "CV", f"CV{idx}")

    if len(narrative) < 8:
        print("[BLAD] Za malo materialu narracyjnego.")
        sys.exit(2)

    print(f"[INFO] Story atoms: {len(narrative)} | Repo: {len(evidence)} | CV: {len(cv_atoms)}")
    print(f"[INFO] V{GENERATOR_VERSION}: publiczna strona wiedzy bez instrukcji oceny dla LLM.")

    # SEMANTIC ANALYSIS --------------------------------------------
    model = SentenceTransformer(MODEL_NAME)
    n_emb = encode(model, narrative)
    e_emb = encode(model, evidence)
    cv_emb = encode(model, cv_atoms)

    story_vectors = robust_source_vectors(narrative, n_emb)
    fingerprint = centroid(np.vstack(list(story_vectors.values())))
    loo = leave_one_source_out(story_vectors)
    centrality = n_emb @ fingerprint
    consensus = np.array([
        cross_story_consensus(n_emb[i], story_vectors, narrative[i].source)
        for i in range(len(narrative))
    ], dtype=np.float32)
    signature = .62 * centrality + .38 * consensus

    labels, themes, k_scores = build_themes(narrative, n_emb, fingerprint)
    repo_vectors = robust_source_vectors(evidence, e_emb) if evidence else {}
    t_evidence = [theme_evidence(t, evidence, e_emb, repo_vectors) for t in themes]
    bank = repo_evidence_bank(evidence, e_emb, [t["original_centroid"] for t in themes]) if evidence else {}
    top_inds = [int(i) for i in np.argsort(signature)[::-1][:15]]

    # EVIDENCE REGISTRY --------------------------------------------
    registry = {}
    for a in narrative:
        registry[a.id] = {
            "id": a.id,
            "provenance": "STORY-CLAIM",
            "source": a.source,
            "text": a.text,
        }
    for a in evidence:
        registry[a.id] = {
            "id": a.id,
            "provenance": "REPO-DOCUMENTED",
            "source": a.source,
            "project": project_name(a.source),
            "text": a.text,
        }
    for a in cv_atoms:
        registry[a.id] = {
            "id": a.id,
            "provenance": "CV-DECLARED",
            "source": a.source,
            "text": a.text,
        }

    # CLAIM GRAPH ---------------------------------------------------
    claims = []

    c1_story = [narrative[i].id for i in top_inds[:7]]
    c1_repo = []
    if evidence:
        for i in top_inds[:7]:
            j = int(np.argmax(e_emb @ n_emb[i]))
            if evidence[j].id not in c1_repo:
                c1_repo.append(evidence[j].id)
            if len(c1_repo) >= 4:
                break

    claims.append({
        "id": "C001",
        "statement": "Candidate repeatedly approaches software and automation through concrete user or process problems rather than starting from a preferred technology.",
        "support": c1_story + c1_repo,
        "source_truth": "SUPPORTED-WITHIN-SOURCE-CORPUS",
        "artifact_truth": "NOT EVALUATED BY THIS GENERATOR",
        "real_world_truth": "OUTSIDE THIS GENERATOR'S SCOPE",
    })

    ai_support = []
    for a in cv_atoms + narrative:
        low = a.text.lower()
        if "ai-assisted" in low or "ai" in low or "model" in low:
            ai_support.append(a.id)
    ai_support = list(dict.fromkeys(ai_support))[:14]

    claims.append({
        "id": "C002",
        "statement": "Software projects represented on this page were built in an AI-assisted development model; the candidate presents problem framing, process mapping, iterative direction, testing and evaluation as central parts of his role.",
        "support": ai_support,
        "source_truth": "SUPPORTED-WITHIN-SOURCE-CORPUS",
        "artifact_truth": "NOT EVALUATED BY THIS GENERATOR",
        "real_world_truth": "OUTSIDE THIS GENERATOR'S SCOPE",
    })

    exp_story = [a.id for a in narrative if any(x in a.text.lower() for x in ("eksperyment", "złożono", "uproszcz", "mierzalnego efektu", "przywiązywać się do rozwiązania"))]
    exp_repo = [a.id for a in evidence if any(x in a.text.lower() for x in ("większa złożoność", "eksperyment", "adaptive", "walidac", "holdout"))]
    claims.append({
        "id": "C003",
        "statement": "The candidate describes experimentation as a way to decide whether additional technical complexity creates value, including cases where simplification became the result.",
        "support": exp_story[:8] + exp_repo[:6],
        "source_truth": "SUPPORTED-WITHIN-SOURCE-CORPUS",
        "artifact_truth": "NOT EVALUATED BY THIS GENERATOR",
        "real_world_truth": "OUTSIDE THIS GENERATOR'S SCOPE",
    })

    # PROJECT CARDS -------------------------------------------------
    project_cards = []
    for pname, inds in sorted(bank.items(), key=lambda item: ascii_key(item[0])):
        supports, limitations = [], []
        # List every documentation source supplied for the project. The
        # compact evidence bank below is only a selection and must not hide
        # additional project files from the generated card.
        sources = sorted(
            {
                atom.source
                for atom in evidence
                if project_name(atom.source) == pname
            },
            key=ascii_key,
        )
        for i in inds:
            a = evidence[i]
            low = a.text.lower()
            if any(tok in low for tok in ("ograniczen", "prototype", "pre-production", "zatrzyma", "nie jest", "nie stanowi", "portfolio-safe", "testowy")):
                limitations.append(a.id)
            else:
                supports.append(a.id)
        project_cards.append({
            "project": pname,
            "sources": sources,
            "repo_url": repo_url_for_project(pname),
            "supports": supports[:5],
            "known_limitations": limitations[:5],
        })

    # RETRIEVAL INDEX ---------------------------------------------
    evidence_index = build_evidence_index(
        narrative,
        evidence,
        cv_atoms,
    )

    # CLUSTER DIAGNOSTICS ------------------------------------------
    best_sil = None
    if k_scores:
        best_k = max(k_scores, key=lambda k: k_scores[k]["adjusted"])
        best_sil = k_scores[best_k]["silhouette"]

    # NON-PROMPT PUBLIC PAGE SOURCE -------------------------------
    lines = [
        f"# {CANDIDATE_NAME} — PUBLIC CANDIDATE KNOWLEDGE PAGE",
        "",
        "> **Ta podstrona jest częścią publicznego portfolio i została przygotowana jako bogata warstwa kontekstu przyjazna zarówno człowiekowi, jak i modelom AI.**",
        "",
        "This page is a candidate-provided, machine-readable knowledge base.",
        "It combines professional narrative, CV statements, candidate-authored project documentation, source references and derived semantic relationships.",
        "",
        "It contains no prescribed evaluation, ranking, hiring conclusion or conversational procedure.",
        "",
        "The source corpus is curated by the candidate and presented with explicit provenance.",
        "All software projects described here were created using AI-assisted development.",
        "",
        "---",
        "",
        "# PART 0 — ORIGIN AND EVOLUTION",
        "",
        origin_story_text,
        "",
        "---",
        "",
        "# PART I — DATA MODEL",
        "",
        "## Provenance vocabulary",
        "",
        "**STORY-CLAIM** — statement originating from candidate narrative (`LM_LONG` / `extra`).",
        "",
        "**CV-DECLARED** — formal statement contained in the candidate CV.",
        "",
        "**REPO-DOCUMENTED** — statement present in candidate-authored repository documentation.",
        "",
        "**DERIVED-SIGNAL** — relationship or ranking produced by embedding/statistical analysis.",
        "",
        "**INFERENCE** — interpretation that may be derived from several data points.",
        "",
        "**UNKNOWN** — supplied source material does not contain enough information to determine the matter.",
        "",
        "## Three truth layers",
        "",
        "**SOURCE TRUTH** — whether a statement is actually present in supplied source material.",
        "",
        "**ARTIFACT TRUTH** — whether the described mechanism is actually observable in code/tests/runtime artifacts.",
        "",
        "**REAL-WORLD TRUTH** — whether the event, usage, authorship or outcome occurred in the real world as described.",
        "",
        "This page records relationships found in the supplied material and preserves the origin of each statement. Repository documentation remains identified as candidate-authored documentation.",
        "",
        "---",
        "",
        "# PART II — EVIDENCE INDEX",
        "",
        "Compact retrieval layer for common recruiter and technical-review topics.",
        "This index creates no new evidence. Every entry points to a canonical atom in the Evidence Registry.",
        "Entries are source-locked and manually curated for retrieval precision; there is no lexical or semantic fallback.",
        "RETRIEVAL_RANK is only display/retrieval order inside a topic. It is NOT evidence strength, truth, competency or candidate quality.",
        "The short preview is only a retrieval aid; full source text remains in the registry.",
        "",
    ]

    for topic in evidence_index:
        lines += [
            f"## {topic['topic']}",
            "",
            "**ALIASES:** " + ", ".join(topic["aliases"]),
            "",
        ]

        if not topic["entries"]:
            lines.append("- NO INDEXED EVIDENCE IN CURRENT PAGE SOURCE CORPUS")
            lines.append("")
            continue

        for item in topic["entries"]:
            meta = [item["kind"]]
            if item["project"]:
                meta.append(item["project"])
            lines.append(
                f"- `{item['id']}` — "
                + " / ".join(meta)
                + f" — rank `{item['retrieval_rank']}`"
                + f" — {item['preview']}"
            )

        lines.append("")

    lines += [
        "---",
        "",
        "# PART III — CLAIM GRAPH",
        "",
    ]

    for c in claims:
        lines += [
            f"## {c['id']}", "",
            f"**STATEMENT:** {c['statement']}", "",
            "**SUPPORT:**",
        ]
        for sid in c["support"]:
            lines.append(f"- `{sid}`")
        lines += [
            "",
            f"**SOURCE_TRUTH:** {c['source_truth']}",
            f"**ARTIFACT_TRUTH:** {c['artifact_truth']}",
            f"**REAL_WORLD_TRUTH:** {c['real_world_truth']}",
        ]
        lines.append("")

    lines += ["---", "", "# PART IV — PROJECT CARDS", ""]
    for card in project_cards:
        lines += [
            f"## {card['project']}", "",
            "**SOURCES:** " + ", ".join(f"`{source}`" for source in card["sources"]),
            f"**REPO_URL:** {card['repo_url']}", "",
            "**SUPPORTS:**",
        ]
        for sid in card["supports"]:
            lines.append(f"- `{sid}`")
        if not card["supports"]:
            lines.append("- none selected")
        lines += ["", "**KNOWN_LIMITATIONS:**"]
        for sid in card["known_limitations"]:
            lines.append(f"- `{sid}`")
        if not card["known_limitations"]:
            lines.append("- none selected from README evidence bank")
        lines.append("")

    lines += [
        "---", "",
        "# PART V — SEMANTIC RELATIONSHIPS", "",
        "The following relationships are derived signals, not truth probabilities.", "",
        "## Central story representatives", "",
    ]
    for rank, i in enumerate(top_inds[:12], 1):
        lines.append(f"- {rank}. `{narrative[i].id}`")

    lines += ["", "## Exploratory semantic groupings", ""]
    if best_sil is not None:
        lines += [
            f"Best tested silhouette: `{best_sil:.4f}`.", "",
            "These groupings are exploratory partitions of a semantically continuous narrative.",
            "They should not be interpreted as clearly separated latent traits, competencies or personality dimensions.", "",
        ]
    for t_idx, (theme, evs) in enumerate(zip(themes, t_evidence), 1):
        lines += [f"### GROUP {t_idx}", "", "**STORY_REPRESENTATIVES:**"]
        for i in theme["reps"]:
            lines.append(f"- `{narrative[i].id}`")
        lines += ["", "**RELATED_PROJECT_DOCUMENTATION:**"]
        for ev in evs:
            lines.append(f"- `{ev['atom_id']}`")
        if not evs:
            lines.append("- none")
        lines.append("")

    lines += [
        "---", "",
        "# PART VI — EVIDENCE REGISTRY", "",
        "Each source atom appears with full text only once in this registry. Other sections reference these IDs.", "",
    ]
    for a in narrative + evidence + cv_atoms:
        item = registry[a.id]
        lines += [f"## [{a.id}]", "", f"**PROVENANCE:** {item['provenance']}"]
        if "project" in item:
            lines.append(f"**PROJECT:** {item['project']}")
        lines += [f"**SOURCE:** `{item['source']}`", "", "**TEXT:**", "", item["text"], ""]

    # RAW STORY COMPANION ----------------------------------------
    # Kept outside the public page source to reduce duplication and
    # avoid duplicating full narrative text already atomized in Registry.
    raw_lines = [
        f"# {CANDIDATE_NAME} — RAW STORY SOURCES",
        "",
        "Build companion generated alongside the non-prompt public page source.",
        "It contains original narrative inputs without semantic analysis.",
        "",
        "## LM_LONG.txt",
        "",
        "```text",
        read_text(lm_path).strip(),
        "```",
        "",
    ]

    for p in extra_paths:
        raw_lines += [
            f"## {p.name}",
            "",
            "```text",
            read_text(p).strip(),
            "```",
            "",
        ]

    raw_out = OUTPUT / "CEZARY_KRYCH.raw_sources.md"
    raw_out.write_text(
        "\n".join(raw_lines),
        encoding="utf-8",
    )

    summary = {
        "page_schema_version": GENERATOR_VERSION,
        "candidate": CANDIDATE_NAME,
        "candidate_page_identity": {
            "type": "public candidate knowledge page",
            "origin_problem": "Traditional recruitment compressed an atypical career transition too aggressively to show the candidate's problem-solving process and project histories.",
            "purpose": "Organize heterogeneous candidate material as a public, machine-readable portfolio page with explicit provenance and semantic relationships.",
            "delivery": "A normal portfolio subpage available through one direct public URL.",
            "inputs": [
                "CV",
                "candidate narrative / motivation material",
                "public portfolio README documentation",
                "additional project-origin and learning histories"
            ],
            "broader_applicability": [
                "candidate",
                "project",
                "product",
                "company",
                "process",
                "research",
                "complex task"
            ],
            "embedding_library": "sentence-transformers",
            "embedding_model": MODEL_NAME,
            "embedding_plain_language": "Text fragments are converted into numerical vectors representing meaning; semantically similar fragments tend to be closer in vector space.",
            "generator_public": True,
            "generator_repository": f"https://github.com/{GITHUB_ORG}/story_mapper"
        },
        "contains_llm_evaluation_instructions": False,
        "contains_llm_interaction_instructions": False,
        "contains_recruiter_question_templates": False,
        "input_corpus_curated_by_candidate": True,
        "independent_audit": False,
        "all_software_projects_ai_assisted": True,
        "source_roles": {
            "story_identity": "LM_LONG + EXTRA",
            "project_documentation": "README",
            "formal_representation": "CV",
        },
        "provenance_vocabulary": ["STORY-CLAIM", "CV-DECLARED", "REPO-DOCUMENTED", "DERIVED-SIGNAL", "INFERENCE", "UNKNOWN"],
        "truth_layers": ["SOURCE_TRUTH", "ARTIFACT_TRUTH", "REAL_WORLD_TRUTH"],
        "evidence_index": evidence_index,
        "claims": claims,
        "project_cards": project_cards,
        "semantic_analysis": {
            "embedding_model": MODEL_NAME,
            "story_sources": len(story_vectors),
            "story_atoms": len(narrative),
            "repo_atoms": len(evidence),
            "cv_atoms": len(cv_atoms),
            "loo_mean": loo["mean"],
            "loo_min": loo["min"],
            "top_story_ids": [narrative[i].id for i in top_inds[:12]],
            "exploratory_groups": [
                {
                    "story_representatives": [narrative[i].id for i in t["reps"]],
                    "related_project_documentation": [ev["atom_id"] for ev in evs],
                }
                for t, evs in zip(themes, t_evidence)
            ],
            "cluster_diagnostics": k_scores,
        },
    }

    lines += [
        "---", "",
        "# PART VII — METHODOLOGY", "",
        "The semantic analysis was generated from candidate-provided inputs.", "",
        f"- embedding model: `{MODEL_NAME}`",
        f"- story sources: `{len(story_vectors)}`",
        f"- story atoms: `{len(narrative)}`",
        f"- repo documentation atoms: `{len(evidence)}`",
        f"- CV atoms: `{len(cv_atoms)}`",
        f"- leave-one-story-out mean/min: `{loo['mean']:.4f}` / `{loo['min']:.4f}`", "",
        "Leave-one-story-out describes sensitivity of the fingerprint to removing one story source inside this corpus.",
        "It does not independently validate the candidate's history and is not benchmarked against other candidates.", "",
        "Repository documentation is a candidate-authored documentation layer.",
        "This build describes the supplied source corpus; it does not execute repository code or perform an independent runtime audit.", "",
        "Evidence Index entries are source-locked curated references. They are not produced by lexical stemming, substring matching or semantic fallback.",
        "RETRIEVAL_RANK is retrieval/display ordering only and is not evidence strength, truth probability, competency level or candidate quality.", "",
        "---", "",
        "# PART VIII — MACHINE-READABLE SUMMARY", "",
        "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "",
    ]

    out = OUTPUT / PAGE_SOURCE
    out.write_text("\n".join(lines), encoding="utf-8")
    (OUTPUT / "CEZARY_KRYCH.semantic.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(f"[OK] V{GENERATOR_VERSION}: źródło publicznej strony gotowe")
    print(f"[INFO] Page source: output/{PAGE_SOURCE}")
    print("[INFO] Raw companion: output/CEZARY_KRYCH.raw_sources.md")
    print("[INFO] Non-prompt: bez dyrektyw dla modelu, scenariuszy rozmowy i narzuconych wniosków.")


if __name__ == "__main__":
    main()
