# Opik Telemetry & Evaluation Lifecycle Architecture

## Staff AI Architect Review — Comprehensive Proposal

---

# PHASE 1: Conceptual Architecture

## Required Reading Summaries

| # | URL | Key Takeaway |
|---|-----|-------------|
| 1 | **Evals Are NOT Audits** (CogniSwitch) | Evals measure quality (probabilistic, noise-tolerant) while audits prove compliance (deterministic, reproducible). Any serious system needs *two layers*: LLM-as-Judge for quality monitoring + deterministic rule-based checks for structural verification. |
| 2 | **LLM Evaluation Frameworks** (Comet) | Opik is a full-stack open-source platform covering tracing → experiments → datasets → online evaluation, positioning it as a single pane of glass across the dev-eval-production lifecycle without needing additional third-party tooling. |
| 3 | **Opik Metrics Overview** | Opik provides Heuristic metrics (Equals, RegexMatch, Levenshtein, ROUGE, IsJson, Readability) and LLM-as-Judge metrics (GEval, Hallucination, AnswerRelevance). Maps directly to our dual-layer philosophy. |
| 4 | **Opik Agent Optimizer SDK** | The Optimizer automates prompt refinement via MetaPrompt/Evolutionary/Bayesian algorithms against datasets and metrics. Requires a *mature, curated dataset* — making it the capstone of the data flywheel once we have sufficient Golden Dataset volume. |

---

## 1. Dual-Layer Evaluation Strategy

The core architectural insight from the required reading is that git-cg needs **two fundamentally different evaluation layers** that serve complementary purposes:

### Layer 1: Deterministic Checks (The "Audit" Layer)

These are binary pass/fail validations that produce identical results on every run. They represent the *minimum bar* a generated commit must clear before it is considered for dataset promotion.

| Check | Description | Implementation |
|-------|-------------|---------------|
| **Header Length** | Full header (emoji + type(scope): description) ≤ 72 chars | `len(header) <= 72` |
| **Description Length** | Primary description ≤ 50 chars | `len(description) <= 50` |
| **Type Validity** | cc_type ∈ CommitType enum | `isinstance(cc_type, CommitType)` |
| **Emoji Matrix Alignment** | gitmoji matches SOP matrix for the selected intent_id | Matrix lookup |
| **Scope Format** | Scope matches `[a-zA-Z0-9_-]+` or is None | Regex |
| **Imperative Mood** | Description starts with a verb in imperative mood | Heuristic NLP check |
| **SemVer Consistency** | SemVer-Impact aligns with cc_type (e.g., feat → MINOR) | Matrix lookup |
| **Breaking Change Completeness** | If `breaking_change=True`, `breaking_change_description` is non-empty | Boolean logic |
| **Body Length** | Body summary (if present) is ≥ 10 chars and ≤ 500 chars | Length check |
| **Trailer Presence** | SemVer-Impact, Change-Types, Changelog-Groups present | String parsing |

These checks are **not** evaluations — they are structural validations. They should run *inline* during generation and as *gates* before dataset promotion.

### Layer 2: Probabilistic Evaluations (The "Quality" Layer)

These use LLM-as-a-Judge (via Opik's GEval) to assess subjective quality dimensions that deterministic checks cannot capture:

| Metric | What It Measures | Opik Implementation |
|--------|-----------------|---------------------|
| **Diff-Commit Semantic Alignment** | Does the description accurately capture what changed in the diff? | Custom GEval with diff as context |
| **Intent Selection Accuracy** | Was the correct cc_type/intent chosen given the diff signals? | GEval comparing chosen intent to diff patterns |
| **Body Quality** | Is the body_summary informative, well-structured, and explanatory? | GEval evaluating body against diff |
| **Scope Precision** | Is the scope appropriately narrow and meaningful? | GEval with file-path context |
| **Conciseness** | Is the description maximally concise without losing meaning? | GEval with character-budget awareness |

> [!IMPORTANT]
> **The project lead's philosophy is correct:** deterministic checks catch structural failures that probabilistic evals will miss (or inconsistently flag). The two layers are not alternatives — they are complementary.

---

## 2. AI vs Human Provenance Classification

This is the most architecturally critical piece. The tool operates as a `prepare-commit-msg` hook, meaning it can observe several distinct provenance states:

### Provenance State Machine

```
┌────────────────────────────────────────────────────────────┐
│                    GIT COMMIT EVENT                        │
│                                                            │
│  commit_source = None/""/"template"                        │
│  ┌──────────────────────┐                                  │
│  │ AI generates message  │──→ User chooses "Commit"        │
│  │ @opik.track fires     │    provenance = AI_GENERATED    │
│  └──────────────────────┘                                  │
│           │                                                │
│           ├──→ User chooses "Edit" (opens editor)          │
│           │    provenance = AI_ASSISTED (human edited)     │
│           │    ┌─ minor edit = AI_ASSISTED_MINOR_EDIT      │
│           │    └─ major edit = AI_ASSISTED_MAJOR_EDIT      │
│           │                                                │
│           └──→ User chooses "Regenerate"                   │
│                provenance = AI_GENERATED (new trace)       │
│                                                            │
│  commit_source = "message" (git commit -m)                 │
│  ┌──────────────────────┐                                  │
│  │ Hook is bypassed      │ provenance = HUMAN_AUTHORED     │
│  │ but we log it anyway  │ (no AI involvement)             │
│  └──────────────────────┘                                  │
│                                                            │
│  commit_source = "commit" (--amend)                        │
│  ┌──────────────────────┐                                  │
│  │ Previous AI message   │ provenance = AMEND_PASSTHROUGH  │
│  │ or human message      │ or AMEND_REGENERATED            │
│  └──────────────────────┘                                  │
└────────────────────────────────────────────────────────────┘
```

### Edit Classification: Minor vs Major

The challenge from the project lead's requirements: *"we need to differentiate between the user adding git references and actual bulk editing of the generated commit message."*

I propose a **Levenshtein Ratio** threshold approach:

- Compute `Levenshtein distance / max(len(ai_generated), len(final_committed))`
- **Minor Edit** (ratio < 0.15): Adding issue refs, fixing typos, tweaking scope
- **Major Edit** (ratio ≥ 0.15): Substantial rewrite of description, type change, scope change
- Additionally: if the **only** changes are trailer additions (issue refs, extra metadata), classify as `AI_ASSISTED_REF_ADDITION` regardless of ratio

This classification becomes a **first-class field** on the Opik trace metadata, enabling filtering and analysis.

---

## 3. Dataset Generation Workflow & Data Flywheel

The data flywheel is the engine that converts raw production traces into curated evaluation datasets:

```
Production Traces ──→ Deterministic Gate ──→ Quality Score ──→ Golden Dataset ──→ Optimizer
       ↑                                                                              │
       └──────────────── Improved Prompt ←────────────────────────────────────────────┘
```

### Stage 1: Collection (Every Hook Invocation)

Every invocation logs to Opik with:
- Input: `diff_output`, `engine`, `model_name`, `system_prompt` (hash)
- Output: `commit_plan` (serialized JSON), `rendered_message`
- Metadata: `provenance`, `thread_id`, `repo_name`, `generation_attempt_number`, `had_regeneration`, `had_edit`, `deterministic_score_card` (all pass/fail checks)

### Stage 2: Deterministic Gating

A post-generation script (or online evaluator) runs all Layer 1 checks. Only traces where **all deterministic checks pass** are candidates for dataset promotion.

### Stage 3: Quality Scoring (Batch Evaluation)

Periodically, run the Layer 2 GEval metrics against gated traces. Traces scoring ≥ 0.8 across all metrics are promoted.

### Stage 4: Golden Dataset Promotion

Promoted traces are added to an Opik Dataset with the schema:
```json
{
  "diff_output": "...",
  "expected_output": "rendered commit message",
  "commit_plan": { ... },
  "provenance": "AI_GENERATED",
  "deterministic_score": { "all_pass": true, "checks": {...} },
  "quality_scores": { "semantic_alignment": 0.92, "intent_accuracy": 0.88 },
  "model": "...",
  "engine": "..."
}
```

### Stage 5: Optimizer (Future)

Once the Golden Dataset exceeds ~100 high-quality samples, use Opik's Agent Optimizer SDK to run MetaPrompt optimization against our system prompt, using the deterministic checks as hard constraints and GEval scores as the objective function.

---

## 4. Opik Platform Utilization Map

### Development

| Feature | Current State | Proposed Usage |
|---------|--------------|----------------|
| **Prompt Library** | Not used | Store versioned system prompts. Each `build_system_prompt()` output should be hashed and registered as a prompt version. |
| **Agent Playground** | Not used | Use for testing prompt variations against specific diffs from the Golden Dataset before deploying. |
| **Prompt Playground** | Not used | Rapid iteration on system prompt phrasing. Connect to the same local MTPLX endpoint. |
| **Optimization Runs** | Not used | **Phase 2 (deferred)**: Once dataset ≥ 100 items, run MetaPrompt/Bayesian optimization to auto-improve prompts. |

### Evaluation

| Feature | Current State | Proposed Usage |
|---------|--------------|----------------|
| **Test Suites** | Not used | Create pytest-integrated test suites that run deterministic + GEval checks against the Golden Dataset as CI gates. |
| **Datasets** | Basic (38 items in JSONL) | Migrate to Opik-managed datasets with full schema. Target 200+ curated items. |
| **Experiments** | Basic setup | Run A/B experiments comparing engines (MTPLX vs oMLX vs OpenAI), models, and prompt versions. |
| **Annotation Queues** | Basic setup | Route low-confidence traces (GEval < 0.7) for human review. Human-approved items get promoted directly to Golden Dataset. |

### Production

| Feature | Current State | Proposed Usage |
|---------|--------------|----------------|
| **Online Evaluation** | Single LLM-as-Judge rule | Replace with a **tiered evaluator chain**: (1) Deterministic score card → (2) GEval semantic alignment. Add provenance as evaluation metadata. |

### Dashboards & Monitoring

| Feature | Proposed Usage |
|---------|----------------|
| **Thread Feedback Scores** | Use `thread_id = repo-{name}` to track quality trends per repository over time. Attach feedback scores when user chooses "Edit" (implicit negative signal) vs "Commit" (implicit positive signal). |
| **Custom Dashboards** | Build dashboards for: (a) Generation success rate by engine, (b) Edit rate over time (declining = improving), (c) Deterministic pass rate, (d) GEval score distribution, (e) Provenance distribution. |

---

## 5. Storage Strategy

| Data | Local | Remote (Opik Cloud) |
|------|-------|---------------------|
| **Raw traces** | Not stored locally (Opik SDK handles) | ✅ Primary storage. All traces flow through `@opik.track`. |
| **Golden Dataset** | `tests/test_data/opik_dataset.jsonl` (backup mirror) | ✅ Opik Datasets (source of truth). |
| **Prompt versions** | Git-tracked in `gitops_agent_sop.json` | ✅ Opik Prompt Library (for playground access). |
| **Deterministic results** | Embedded in trace metadata | ✅ Available via trace metadata in Opik. |
| **Evaluation results** | Not stored locally | ✅ Opik Experiments. |
| **Edit diffs** | Not stored | ✅ Logged as trace metadata (AI-generated vs final committed). |

> [!TIP]
> The local JSONL dataset serves as a **backup mirror** and enables offline evaluation (e.g., `eval_commit_message.py` against a local MTPLX server). The Opik cloud dataset is the authoritative source.

---

## 6. Start-Logging Point Recommendation

### Current State

The `@opik.track` decorator is on `generate_commit_message()` (line 358 of [main.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/main.py#L358)). This traces only the LLM call and its immediate inputs/outputs.

### Recommendation: Move the Start-Logging Point to `_run_commit_generation()`

| Aspect | Current (`generate_commit_message`) | Proposed (`_run_commit_generation`) |
|--------|--------------------------------------|--------------------------------------|
| **What's traced** | Single LLM call | Entire lifecycle: diff extraction → prompt building → generation → review → edit → final commit |
| **Regeneration visibility** | Each regen is a disconnected trace | Regeneration loop is visible as child spans within one parent trace |
| **Edit tracking** | Not captured | Final committed message captured as trace output, enabling edit diff |
| **Provenance** | Not captured | Deterministically classified from the review flow outcome |
| **Performance** | Traces only LLM latency | Traces end-to-end latency (diff+prompt+LLM+review) |
| **Review metadata** | Not captured | Issue references, regeneration guidance, active directives all logged |

#### Pros of Moving Up

1. **Complete lifecycle visibility**: One trace per hook invocation, with child spans for each generation attempt
2. **Edit tracking becomes trivial**: Compare `review_state.render()` (AI output) with the final file contents
3. **Regeneration correlation**: Multiple calls within a single review loop share a parent trace
4. **Provenance classification**: The review flow outcome (`"Commit"`, `"Edit"`, `"Cancel"`) is known at the `_run_commit_generation` level, not at the LLM call level
5. **Review metadata capture**: Issue references, regeneration guidance, directive overrides — all are scope-local to `_run_commit_generation`

#### Cons of Moving Up

1. **Trace duration**: Traces will include human think-time during interactive review (could be minutes). Mitigation: log `llm_latency_ms` separately in metadata.
2. **Non-generation invocations**: Calls that exit early (e.g., `commit_source not in GENERATING_SOURCES`) would need to be excluded or traced minimally. Mitigation: conditional decoration.
3. **Existing trace continuity**: Changing the trace boundary means historical traces won't be directly comparable. Mitigation: Add a `schema_version` metadata field; keep `generate_commit_message` as a child span.

#### Verdict

**Move the start-logging point to `_run_commit_generation()`** and convert `generate_commit_message()` from a top-level `@opik.track` to a **child span**. This gives us full lifecycle observability without losing the granular LLM call data.

---

# PHASE 2: Codebase Mapping & Implementation

## Codebase Understanding

After reading all source files, here is the relevant architecture:

| File | Role | Opik Relevance |
|------|------|---------------|
| [main.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/main.py) | Core CLI + hook logic. `_run_commit_generation()` is the lifecycle. `generate_commit_message()` has `@opik.track`. | **Primary integration target.** |
| [models.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/models.py) | Pydantic models: `CommitPlan`, `CommitIntent`, `IssueReference` | Deterministic validation source. |
| [regeneration.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/regeneration.py) | Semantic contract resolution for regeneration | Regeneration correlation metadata. |
| [intent.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/intent.py) | Diff signal extraction + intent ranking | Input telemetry. |
| [interaction.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/interaction.py) | TUI prompts via gum | Review action capture. |
| [sop.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/sop.py) | GitOps SOP matrix loader | Matrix version tracking. |
| [setup_opik_eval_rule.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/setup_opik_eval_rule.py) | Single online eval rule | Needs expansion to tiered evaluator chain. |
| [compile_opik_dataset.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/compile_opik_dataset.py) | Trace → dataset compiler | Needs deterministic gating + quality scoring. |
| [eval_commit_message.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/eval_commit_message.py) | Local GEval evaluation | Needs multiple metrics + deterministic layer. |

---

## Proposed New Modules

### 1. `src/git_cg/telemetry.py` [NEW]

The telemetry orchestration module. Encapsulates all Opik-specific logic outside of `main.py`:

```python
"""Opik telemetry orchestration for git-cg lifecycle tracking."""

import hashlib
import enum
from dataclasses import dataclass, field, asdict
from typing import Any

import opik
from opik import opik_context


class Provenance(enum.StrEnum):
    """Classification of who authored the final commit message."""
    AI_GENERATED = "ai_generated"           # User accepted without edits
    AI_ASSISTED_MINOR_EDIT = "ai_assisted_minor_edit"  # Minor tweaks (< 15% change)
    AI_ASSISTED_MAJOR_EDIT = "ai_assisted_major_edit"  # Substantial rewrite (≥ 15%)
    AI_ASSISTED_REF_ADDITION = "ai_assisted_ref_addition"  # Only added issue refs
    HUMAN_AUTHORED = "human_authored"       # git commit -m (no AI involved)
    AMEND_PASSTHROUGH = "amend_passthrough" # Amend without regeneration
    AMEND_REGENERATED = "amend_regenerated" # Amend with AI regeneration


@dataclass
class DeterministicScoreCard:
    """Binary pass/fail structural validation results."""
    header_length_ok: bool = False
    description_length_ok: bool = False
    type_valid: bool = False
    emoji_matrix_aligned: bool = False
    scope_format_ok: bool = False
    semver_consistent: bool = False
    breaking_change_complete: bool = False
    trailer_present: bool = False
    body_length_ok: bool = False  # True if no body, or body within bounds

    @property
    def all_pass(self) -> bool:
        return all(asdict(self).values())

    @property
    def failed_checks(self) -> list[str]:
        return [k for k, v in asdict(self).items() if not v]


@dataclass
class GenerationTelemetry:
    """Telemetry data collected across one hook invocation lifecycle."""
    repo_name: str = ""
    engine: str = ""
    model_name: str = ""
    system_prompt_hash: str = ""
    generation_attempt: int = 0
    total_attempts: int = 0
    had_regeneration: bool = False
    had_edit: bool = False
    provenance: Provenance = Provenance.AI_GENERATED
    review_action: str = ""
    score_card: DeterministicScoreCard = field(default_factory=DeterministicScoreCard)
    issue_references_added: int = 0
    regeneration_guidance_provided: bool = False
    active_directives: dict[str, str] = field(default_factory=dict)
    diff_char_count: int = 0
    diff_file_count: int = 0
    primary_language: str | None = None
    llm_latency_ms: float = 0.0


def compute_prompt_hash(prompt: str) -> str:
    """SHA-256 hash of the system prompt for version tracking."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def classify_provenance(
    ai_generated_message: str,
    final_message: str,
    review_action: str,
    commit_source: str | None,
) -> Provenance:
    """Classify the provenance of the final committed message."""
    if commit_source == "message":
        return Provenance.HUMAN_AUTHORED
    if commit_source == "commit":
        if ai_generated_message == final_message:
            return Provenance.AMEND_PASSTHROUGH
        return Provenance.AMEND_REGENERATED

    if review_action == "Edit":
        return _classify_edit(ai_generated_message, final_message)
    return Provenance.AI_GENERATED


def _classify_edit(original: str, edited: str) -> Provenance:
    """Classify edit magnitude using Levenshtein ratio."""
    # Check if changes are only in trailers (issue refs)
    orig_lines = original.strip().split('\n')
    edit_lines = edited.strip().split('\n')

    # If the only additions are issue reference lines, classify as ref addition
    added_lines = set(edit_lines) - set(orig_lines)
    removed_lines = set(orig_lines) - set(edit_lines)

    issue_ref_patterns = {"Resolves #", "Refs #", "Closes #", "Fixes #"}
    if added_lines and not removed_lines:
        if all(any(line.strip().startswith(p) for p in issue_ref_patterns) for line in added_lines):
            return Provenance.AI_ASSISTED_REF_ADDITION

    # Levenshtein ratio
    distance = _levenshtein_distance(original, edited)
    max_len = max(len(original), len(edited), 1)
    ratio = distance / max_len

    if ratio < 0.15:
        return Provenance.AI_ASSISTED_MINOR_EDIT
    return Provenance.AI_ASSISTED_MAJOR_EDIT


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def run_deterministic_checks(commit_plan, rendered_message: str) -> DeterministicScoreCard:
    """Run all deterministic structural validations."""
    import re
    from git_cg.sop import get_gitmoji_matrix

    card = DeterministicScoreCard()
    pi = commit_plan.primary_intent

    # Header length
    scope_str = f"({pi.scope})" if pi.scope else ""
    breaking = "!" if commit_plan.breaking_change else ""
    header = f"{pi.gitmoji} {pi.cc_type.value}{scope_str}{breaking}: {pi.description}"
    card.header_length_ok = len(header) <= 72

    # Description length
    card.description_length_ok = len(pi.description) <= 50

    # Type validity
    from git_cg.models import CommitType
    card.type_valid = isinstance(pi.cc_type, CommitType)

    # Emoji matrix alignment
    matrix = get_gitmoji_matrix()
    if matrix:
        entry = next((e for e in matrix if e.get("intent_id") == pi.intent_id), None)
        card.emoji_matrix_aligned = entry is not None and entry.get("emoji") == pi.gitmoji
    else:
        card.emoji_matrix_aligned = True  # No matrix = no constraint

    # Scope format
    if pi.scope is None:
        card.scope_format_ok = True
    else:
        card.scope_format_ok = bool(re.match(r'^[a-zA-Z0-9_-]+$', pi.scope))

    # SemVer consistency
    if matrix:
        entry = next((e for e in matrix if e.get("intent_id") == pi.intent_id), None)
        if entry:
            card.semver_consistent = entry.get("semver_impact") == pi.semver_impact.value
        else:
            card.semver_consistent = True
    else:
        card.semver_consistent = True

    # Breaking change completeness
    if commit_plan.breaking_change:
        card.breaking_change_complete = bool(commit_plan.breaking_change_description)
    else:
        card.breaking_change_complete = True

    # Trailer presence
    card.trailer_present = all(
        trailer in rendered_message
        for trailer in ["SemVer-Impact:", "Change-Types:", "Changelog-Groups:"]
    )

    # Body length
    if commit_plan.body_summary:
        body_len = len(commit_plan.body_summary)
        card.body_length_ok = 10 <= body_len <= 500
    else:
        card.body_length_ok = True

    return card


def flush_trace_metadata(telemetry: GenerationTelemetry) -> None:
    """Update the current Opik trace with collected telemetry data."""
    opik_context.update_current_trace(
        metadata={
            "provenance": telemetry.provenance.value,
            "engine": telemetry.engine,
            "model": telemetry.model_name,
            "system_prompt_hash": telemetry.system_prompt_hash,
            "generation_attempts": telemetry.total_attempts,
            "had_regeneration": telemetry.had_regeneration,
            "had_edit": telemetry.had_edit,
            "review_action": telemetry.review_action,
            "deterministic_checks": asdict(telemetry.score_card),
            "deterministic_all_pass": telemetry.score_card.all_pass,
            "issue_references_added": telemetry.issue_references_added,
            "regeneration_guidance_provided": telemetry.regeneration_guidance_provided,
            "active_directives": telemetry.active_directives,
            "diff_char_count": telemetry.diff_char_count,
            "diff_file_count": telemetry.diff_file_count,
            "primary_language": telemetry.primary_language,
            "llm_latency_ms": telemetry.llm_latency_ms,
            "repo_name": telemetry.repo_name,
            "_opik_graph_definition": {
                "format": "mermaid",
                "data": (
                    "graph TD; Hook[Git Hook] --> Diff[Diff Extract]; "
                    "Diff --> Prompt[Prompt Build]; Prompt --> LLM[LLM Call]; "
                    "LLM --> Review[Interactive Review]; Review --> Commit[Final Commit]; "
                    "Review -->|Regenerate| LLM; Review -->|Edit| Commit;"
                ),
            },
        },
        tags=[
            telemetry.provenance.value,
            telemetry.engine,
            f"attempts:{telemetry.total_attempts}",
        ],
    )
```

---

### 2. `src/git_cg/eval_metrics.py` [NEW]

Custom Opik metrics tailored to git-cg's domain:

```python
"""Custom Opik evaluation metrics for git-cg commit message quality."""

from opik.evaluation.metrics import GEval


# Metric 1: Diff-Commit Semantic Alignment
diff_semantic_alignment = GEval(
    name="DiffSemanticAlignment",
    task_introduction=(
        "You are an expert software engineer reviewing a generated "
        "Conventional Commit message against its source git diff."
    ),
    evaluation_criteria="""
Evaluate whether the Generated Commit Message accurately and completely 
captures the changes shown in the Git Diff.

Score 1.0 if the message:
- Correctly identifies the primary type of change (feat, fix, refactor, etc.)
- Accurately describes what was changed
- Uses appropriate scope if files are concentrated in one area
- Doesn't claim changes that aren't in the diff

Score 0.0 if the message:
- Describes changes not present in the diff
- Misidentifies the type of change
- Misses the primary change entirely
""",
)

# Metric 2: Intent Selection Accuracy
intent_selection_accuracy = GEval(
    name="IntentSelectionAccuracy",
    task_introduction=(
        "You are evaluating whether the correct Conventional Commit type "
        "was selected for a given code change."
    ),
    evaluation_criteria="""
Given the git diff, evaluate if the chosen commit type is the most 
appropriate classification:

- feat: New features or capabilities
- fix: Bug fixes
- refactor: Code restructuring without behavior change
- docs: Documentation only
- style: Formatting, whitespace, etc.
- perf: Performance improvements
- test: Test additions or changes
- build: Build system or dependency changes
- ci: CI/CD configuration changes
- chore: Maintenance tasks

Score 1.0 for perfect type selection, 0.5 for acceptable but suboptimal, 
0.0 for clearly incorrect.
""",
)

# Metric 3: Conciseness Quality
conciseness_quality = GEval(
    name="ConcisenessQuality",
    task_introduction=(
        "You are evaluating the conciseness and clarity of a commit "
        "message description."
    ),
    evaluation_criteria="""
Evaluate whether the primary description is maximally concise while 
remaining clear and informative:

Score 1.0 if: Uses imperative mood, is under 50 characters, every word 
adds meaning, no filler words.
Score 0.5 if: Mostly concise but has minor redundancy or slightly exceeds 
ideal length.
Score 0.0 if: Verbose, uses past tense, contains filler words, or is 
too vague to be useful.
""",
)

ALL_QUALITY_METRICS = [
    diff_semantic_alignment,
    intent_selection_accuracy,
    conciseness_quality,
]
```

---

## Specific File Modifications

### 1. [main.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/main.py) — Core Changes

#### Change 1: Move `@opik.track` from `generate_commit_message` to `_run_commit_generation`

```diff
-@opik.track(project_name="gitCommitGenerator")
 def generate_commit_message(
     client: instructor.Instructor,
     diff_output: str,
     model_name: str,
     system_prompt: str,
     active_directives: dict[str, str] | None = None,
     residual_guidance: str | None = None,
     **kwargs,
 ) -> CommitPlan:
```

Keep `generate_commit_message` as a **manually created span** inside the parent trace:

```python
def generate_commit_message(...) -> CommitPlan:
    import time
    start_time = time.monotonic()
    
    # ... existing retry logic ...
    
    elapsed_ms = (time.monotonic() - start_time) * 1000
    return commit_result, elapsed_ms  # Return timing alongside result
```

#### Change 2: Instrument `_run_commit_generation` as the root trace

```python
@opik.track(project_name="gitCommitGenerator")
def _run_commit_generation(
    commit_msg_file: str,
    commit_source: str | None,
    ...
) -> bool:
    from git_cg.telemetry import (
        GenerationTelemetry, compute_prompt_hash, 
        classify_provenance, run_deterministic_checks,
        flush_trace_metadata,
    )
    
    telemetry = GenerationTelemetry(
        engine=engine,
        repo_name=repo_name,  # from existing code
        diff_char_count=len(diff_output),
        diff_file_count=diff_output.count("diff --git"),
        primary_language=detect_primary_language(diff_output),
    )
    
    # ... existing generation loop ...
    
    # After generation:
    telemetry.system_prompt_hash = compute_prompt_hash(system_prompt)
    telemetry.generation_attempt += 1
    
    # After review:
    ai_generated_message = review_state.render()
    
    # Read final message after edit (if applicable)
    if action == "Edit":
        with open(commit_msg_file) as f:
            final_message = f.read()
        telemetry.had_edit = True
    else:
        final_message = ai_generated_message
    
    telemetry.review_action = action
    telemetry.provenance = classify_provenance(
        ai_generated_message, final_message, action, commit_source
    )
    telemetry.score_card = run_deterministic_checks(
        review_state.commit_plan, ai_generated_message
    )
    telemetry.total_attempts = telemetry.generation_attempt
    telemetry.issue_references_added = len(review_state.issue_references)
    telemetry.regeneration_guidance_provided = review_state.regeneration_guidance is not None
    telemetry.active_directives = review_state.active_directives
    
    flush_trace_metadata(telemetry)
    
    # Log the AI-generated and final messages as trace output
    opik_context.update_current_trace(
        output={
            "ai_generated_message": ai_generated_message,
            "final_committed_message": final_message,
            "commit_plan": review_state.commit_plan.model_dump(),
        }
    )
```

#### Change 3: Log human-authored commits (non-generating sources)

Currently, when `commit_source not in GENERATING_SOURCES`, the function exits immediately. We should log this as a `HUMAN_AUTHORED` event:

```python
if commit_source not in GENERATING_SOURCES:
    if amend_regenerate and commit_source == "commit":
        pass  # proceed
    else:
        # Log the human-authored commit for provenance tracking
        _log_human_authored_commit(commit_msg_file, commit_source, engine)
        raise typer.Exit(code=0)
```

```python
def _log_human_authored_commit(commit_msg_file: str, source: str, engine: str):
    """Log a non-AI-generated commit to Opik for provenance tracking."""
    try:
        with open(commit_msg_file) as f:
            message = f.read()
    except OSError:
        return
    
    opik.track(
        project_name="gitCommitGenerator",
        name="human_authored_commit",
        input={"commit_source": source},
        output={"message": message},
        metadata={
            "provenance": "human_authored",
            "commit_source": source,
        },
        tags=["human_authored"],
    )
    opik.flush_tracker()
```

---

### 2. [setup_opik_eval_rule.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/setup_opik_eval_rule.py) — Expand to Tiered Evaluator Chain

Replace the single rule with multiple rules:

**Rule 1: Deterministic Structure Check** (sampling rate: 1.0)
- This should be a **code-based evaluator**, not LLM-as-Judge
- Checks: header length, type validity, trailer presence
- Returns binary 0.0 or 1.0

**Rule 2: Semantic Alignment** (sampling rate: 0.25)
- GEval-based (the existing rule, improved)
- Uses the `diff_semantic_alignment` criteria from our metrics module
- Sampling at 25% to manage costs

**Rule 3: Provenance Classifier** (sampling rate: 1.0)
- Code-based evaluator that reads the `provenance` metadata field
- Tags the trace with its provenance category for dashboard filtering

---

### 3. [compile_opik_dataset.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/compile_opik_dataset.py) — Add Deterministic Gating

```python
def compile_dataset():
    """Compile Opik traces into a curated Golden Dataset with deterministic gating."""
    # ... existing trace loading ...
    
    for trace in traces:
        # Gate 1: Deterministic checks must all pass
        metadata = trace.get("metadata", {})
        det_checks = metadata.get("deterministic_checks", {})
        if not det_checks.get("all_pass", False):
            skipped_deterministic += 1
            continue
        
        # Gate 2: Must be AI_GENERATED provenance (not human-authored or heavily edited)
        provenance = metadata.get("provenance", "")
        if provenance not in ("ai_generated", "ai_assisted_minor_edit"):
            skipped_provenance += 1
            continue
        
        # Gate 3: If quality scores exist, must meet threshold
        quality = metadata.get("quality_scores", {})
        if quality and quality.get("semantic_alignment", 1.0) < 0.8:
            skipped_quality += 1
            continue
        
        # Promote to dataset
        record = {
            "diff_output": diff,
            "expected_output": rendered_message,
            "commit_plan": output_data,
            "provenance": provenance,
            "model": metadata.get("model", ""),
            "engine": metadata.get("engine", ""),
        }
        ...
```

---

### 4. [eval_commit_message.py](file:///Users/admin/dev/activeProjects/gitCommitGenerator/scripts/eval_commit_message.py) — Multi-Metric Evaluation

```python
from git_cg.eval_metrics import ALL_QUALITY_METRICS
from git_cg.telemetry import run_deterministic_checks

def evaluation_task(item):
    # ... existing generation logic ...
    
    # Run deterministic checks as part of evaluation
    from git_cg.models import CommitPlan
    commit_plan_data = item.get("commit_plan", {})
    
    return {
        "input": diff_output,
        "output": result_string,
        "expected_output": expected,
        "context": [diff_output],  # For AnswerRelevance-style metrics
    }

def main():
    evaluate(
        dataset=dataset,
        task=evaluation_task,
        scoring_metrics=ALL_QUALITY_METRICS,  # All 3 metrics
    )
```

---

## Hook Invocation Correlation Mechanism

### Problem

A single `git commit` can trigger multiple hook invocations (prepare-commit-msg, commit-msg, post-commit). The regeneration loop within `_run_commit_generation` produces multiple LLM calls within a single invocation. How do we correlate all of this?

### Solution: Three-Level Correlation

```
Level 1: thread_id = "repo-{repo_name}"
    └── Correlates ALL commits for a repository over time
    
Level 2: trace_id = auto-generated by @opik.track on _run_commit_generation
    └── Correlates one complete hook invocation lifecycle
    
Level 3: span_id = auto-generated for each generate_commit_message call
    └── Correlates each individual LLM call within a regeneration loop
```

Implementation:

```python
# In _run_commit_generation:
opik_context.update_current_trace(
    thread_id=f"repo-{repo_name}",
    metadata={
        "invocation_id": str(uuid.uuid4()),  # Unique per hook invocation
        "generation_loop_index": generation_attempt,
    }
)
```

The `thread_id` enables Opik's thread-level feedback scores — you can see quality trends for a specific repository over time.

---

## Opik Feature Configurations

### 1. Prompt Library Setup

Register the system prompt template in Opik's Prompt Library. Each time `build_system_prompt()` produces a new hash, log it:

```python
# In build_system_prompt, after constructing the prompt:
prompt_hash = compute_prompt_hash(system_prompt)
# Log to Opik as a prompt version (via API or SDK)
```

### 2. Annotation Queue Configuration

Create an annotation queue for traces that:
- Have `deterministic_all_pass = True` BUT
- Have GEval semantic alignment < 0.7
- Route these for human review to improve the Golden Dataset

### 3. Feedback Score Integration

After the review action is determined:

```python
if action == "Commit":
    opik_context.update_current_trace(
        feedback_scores=[{"name": "user_acceptance", "value": 1.0}]
    )
elif action == "Edit":
    opik_context.update_current_trace(
        feedback_scores=[{"name": "user_acceptance", "value": 0.5}]
    )
elif action == "Cancel":
    opik_context.update_current_trace(
        feedback_scores=[{"name": "user_acceptance", "value": 0.0}]
    )
elif action == "Regenerate":
    opik_context.update_current_trace(
        feedback_scores=[{"name": "user_acceptance", "value": 0.25}]
    )
```

This creates an implicit **reinforcement signal** — traces where users consistently accept without edits are strong candidates for the Golden Dataset.

### 4. Custom Dashboard Specification

Configure dashboards tracking:

| Dashboard | Metrics | Dimensions |
|-----------|---------|------------|
| **Generation Health** | Success rate, avg latency, error rate | By engine, model, time |
| **Quality Trend** | GEval scores (rolling 7-day average) | By engine, model |
| **User Acceptance** | Accept/Edit/Cancel/Regenerate ratio | By time, repo |
| **Provenance Distribution** | AI_GENERATED vs AI_ASSISTED vs HUMAN | By time |
| **Deterministic Pass Rate** | % of generations passing all checks | By check, time |
| **Data Flywheel Progress** | Golden Dataset size, promotion rate | By time |

---

## Novel Improvements Beyond Current Scope

### 1. **Confidence-Gated Auto-Accept**

If a commit plan scores 1.0 on *all* deterministic checks AND the user has historically accepted similar diffs (tracked via thread-level feedback), skip the interactive review and auto-commit. This transforms git-cg from a "generate and review" tool into a "trust-calibrated autonomous agent."

### 2. **Cross-Repository Prompt Transfer**

Use Opik Experiments to test whether prompts optimized on Repository A's Golden Dataset perform well on Repository B. If transfer learning works, the Optimizer can train on pooled datasets.

### 3. **Regression Detection via Thread Feedback**

Monitor the `user_acceptance` feedback score per `thread_id`. If the rolling average drops below a threshold (e.g., from 0.9 to 0.6), automatically trigger an alert and queue the recent traces for human review.

### 4. **Diff Fingerprinting for Deduplication**

Before adding a trace to the Golden Dataset, compute a structural fingerprint of the diff (file types changed, change magnitude, operation types) and check for near-duplicates. This ensures dataset diversity and prevents overfitting the Optimizer to repetitive patterns.

### 5. **A/B Prompt Experimentation Framework**

Use Opik Experiments to set up automated A/B tests:
- Run two prompt variants against the same Golden Dataset
- Compare GEval scores + deterministic pass rates
- Auto-promote the winner to the Prompt Library

### 6. **Post-Commit Hook for Ground Truth Capture**

Add a `post-commit` hook that reads the *actual committed message* (after any manual edits in the editor) and logs it back to the Opik trace. This captures the true ground truth, which is invaluable for training data — especially for cases where the user chose "Edit" in the interactive review.

```python
# post-commit hook
def post_commit_hook():
    """Capture the final committed message for ground truth tracking."""
    final_msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%B"], text=True
    ).strip()
    
    # Read the trace ID from a temp file written by prepare-commit-msg
    trace_id = read_trace_id_from_temp()
    if trace_id:
        client = opik.Opik()
        client.log_traces_feedback_scores([{
            "id": trace_id,
            "name": "ground_truth_message",
            "value": 1.0,
            "reason": final_msg,
        }])
```
