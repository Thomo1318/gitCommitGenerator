# git-cg — Codebase & Architecture Review

> Reviewing agent report. Date: 2026-06-01. Scope: architecture, security, performance, code smells, TODO prioritisation, and actionable improvements.

## 1. Executive Summary

`git-cg` is in a solid but transitional state. The Python rewrite (`src/git_cg`) is the real, working engine; a parallel **legacy zsh/Node implementation** still litters the repo and the README/usage specs, creating significant confusion about the source of truth. The core "structured extraction via Instructor + Pydantic + SOP matrix" design is sound and genuinely elegant — the double validation (Pydantic on generation, Node gatekeeper on `commit-msg`) is a real strength.

However, there are **two blocking issues before any public release**:

1. **A real leaked secret** (`AGENTOPS_API_KEY`) is committed in `build/lib/git_cg/main.py` and lives in git history (commits `8f44852`, `155116a`, `3b2e2ee`). It is also baked into your repomix artifact.
2. **Portability is effectively zero** — the tool hard-codes your personal 1Password Environment UUID, assumes `os.getcwd()` is the repo root, and is wired to your global mise setup.

Everything else is iteration. Details below.

---

## 2. Critical / Blocking Findings

### 2.1 Leaked AgentOps API key (SECURITY — must fix before publishing)
* File: `build/lib/git_cg/main.py` line 28 contains a hardcoded fallback: `os.environ.get('AGENTOPS_API_KEY', '233574f8-620e-44c6-b64c-f25e4156f7b3')`.
* This key is present in:
  * `build/` (currently untracked — `build/` is gitignored, good)
  * **git history** at commits `8f44852` and `155116a` (`git log -S` confirms it)
  * **`repomix-output.xmlgitCommitGenerator.xml`** (1 occurrence) — so the artifact you pasted to me, and any you publish, leaks it.
* Action required:
  1. **Revoke/rotate that AgentOps key immediately** regardless of next steps — treat it as compromised.
  2. Rewrite git history before any public push (`git filter-repo --replace-text` or BFG) to purge the literal string from all commits.
  3. Regenerate `repomix-output.xml*` after the cleanup, and add `repomix-output*` to `.gitignore` (it is a 120 MB artifact that should never be committed).
* Note: `agentops` has been removed from the live `src/` code (good — current `main.py` uses Opik only), so this is a history/artifact hygiene problem, not a live-code problem. But a hardcoded secret in history is still a leaked secret.

### 2.2 The 120 MB repomix artifact is in the working tree
* `repomix-output.xmlgitCommitGenerator.xml` is 120,791,178 bytes. It is not gitignored. It contains the leaked key. It should be generated on demand (TODO already notes automating repomix) and `.gitignore`d. Confirm it is not in history with `git log --all -- 'repomix-output*'`.

### 2.3 `os.getcwd()`-based SOP resolution is fragile and breaks the hook
* In `main.py`, `models.py`, and `release.py`, the SOP path is resolved from `os.getcwd()`:
  ```python
  sop_path = os.path.join(os.getcwd(), "config", "gitops_agent_sop.json")
  ```
* When invoked as a git `prepare-commit-msg` hook, `cwd` is the **target repo's root**, not git-cg's install dir. So when you run `git commit` in *any other project*, the SOP file won't be found, the Pydantic matrix validator silently `pass`es (see 3.1), and the system prompt loses the entire gitmoji matrix. The tool degrades to a generic LLM prompt with no SOP enforcement, and you won't be told.
* The fallback path `config/gitCommitGenerator/config/gitops_agent_sop.json` is a brittle hack that only works in one specific nesting.
* **Fix**: Resolve the SOP relative to the package (`importlib.resources` / `Path(__file__)`), or via an env/config override. Ship the SOP as package data. This is arguably the single most important architectural fix and underpins the whole "portability" TODO.

---

## 3. Code Smells & Correctness Issues

### 3.1 Silent failure swallowing in the matrix validator
`models.py::validate_and_correct_matrix` wraps everything in `except Exception: pass`. If the SOP can't be loaded (the common case outside git-cg's own repo — see 2.3), validation is silently skipped. The `except ValueError: raise` correctly re-raises genuine validation errors, but a missing/corrupt SOP becomes invisible. At minimum, log it under `--verbose`; better, fail loud if the SOP was expected but missing.

### 3.2 Pydantic model performs file I/O on every validation
The matrix validator opens and parses `gitops_agent_sop.json` *inside* the model validator, which Instructor may call on every retry. This couples the data model to the filesystem and re-reads/re-parses JSON repeatedly. Load the SOP once (module-level `@functools.cache` or pass it in via validation context using Pydantic's `model_validate(..., context=...)`). This is both a smell (separation of concerns) and a minor perf issue.

### 3.3 Stray debug code shipped
* `main.py` ends with `print("IT WORKED!")` *after* `app()` — dead code, but sloppy and would print on import in some paths. Remove.
* `commit` (root file) appears to be a stray scratch commit message file. Remove or move to `docs/`.

### 3.4 Duplicate, divergent release logic
There are **two** release engines: `src/git_cg/release.py` (Python, used by `release` command) and `scripts/cut_release.mjs` (Node). They implement overlapping SemVer/changelog logic with subtly different rules:
* Node `cut_release.mjs` defaults `bumpType = "PATCH"` and only matches **unicode emoji** at the start (`\p{Emoji_Presentation}...`), so shortcode commits (`:sparkles:`) are skipped.
* Python `release.py` defaults to `NONE` and has a regex `^[^\s]+\s+([a-z]+)` that is more permissive.
* They will produce **different versions for the same history**. Pick one (Python, to match the engine) and delete the other, or clearly demote the Node one.

### 3.5 `parse_commit_impact` breaking-change detection is weak
`"!" in subject.split(":")[0]` will misfire on any subject whose pre-colon segment contains `!` (e.g. an emoji rendering or a scope with punctuation), and won't catch a `BREAKING CHANGE:` footer that's in the body (it only sees `%s` subject in `calculate_global_bump`, but `get_commits_since` formats `%s|%b` and then `release.py` splits on `|` and only uses `[0]`). Net effect: footer-based breaking changes are not detected by the Python path. Parse the body too.

### 3.6 `rtk` fallback is logically inverted vs. the README claim
README says rtk gives "sub-second inference" and "up to 90%" compression as a core path. The actual code only invokes rtk **when the diff exceeds 50 000 chars** (`if len(diff_output) > max_chars and has_rtk`). For typical commits rtk never runs. Either the README oversells rtk, or the routing should compress earlier. Decide the intended behaviour and align code + docs. Also: after rtk compresses, you re-check `> max_chars` and hard-truncate — if rtk fails to get under 50k you truncate mid-diff, which can corrupt the diff context.

### 3.7 Diff exclusion list is bespoke/hardcoded
The `:(exclude)*zensical*`, `:(exclude)*auxly*` pathspecs are personal. Move exclusions to config (ties into the config-file TODO).

### 3.8 Version drift across manifests
* `pyproject.toml` → `version = "0.1.7"`, `requires-python = ">=3.12"`
* `mise.toml` → `python = "3.14"`
* `package.json` → `version = "1.0.0"`
* README says "Python 3.12"; handoff says "Python 3.14+".
Three different versions and two different Python baselines. Pick one source of truth (this is exactly what the "version injection" TODO should solve, but fix the manual drift now).

### 3.9 Engine routing is brittle
`get_ai_client` maps `omlx|mtplx|mlx` all to an OpenAI-compatible client and derives the env prefix as `MTPLX` only for exact `"mtplx"`, else `OMLX`. `mlx` silently uses `OMLX_*`. The "Unsupported engine" branch makes the Gemini/Claude/OpenAI TODO impossible without refactor. Recommend a small registry/strategy pattern (`dict[str, EngineConfig]`) now — it's cheap and unblocks the "other backends" roadmap.

### 3.10 `commit_source` is accepted but unused
The hook passes `{{source}}` (`message`, `template`, `merge`, `squash`, `commit`, `amend`) but the code never branches on it. You should **skip generation** when `source` is `merge`, `squash`, or `commit` (amend/-c), otherwise git-cg will clobber legitimate merge/amend messages. This is a latent bug that will bite real users.

---

## 4. Security Model Review (Zero-Plaintext)

The intent is good; the implementation has gaps:

* **Hardcoded personal 1P Environment UUID** in `with_1p_env.sh` (`ce3a5m2atri7cxq7mdvofergt4`). This is not a secret per se, but it's a hard portability blocker and ties the tool to your vault. Make it configurable (`GIT_CG_OP_ENV` env var with a documented fallback).
* The script does `eval "$(... op environment read ...)"` then `exec "$@"`. `eval` of remote/dynamic content is generally a smell; for 1Password output it's acceptable, but document the trust assumption. Prefer `op run --env-file` or `op inject` where possible (your own TODO already lists `SecretStr`/`pydantic-settings` — good direction).
* For a **public** tool, the entire 1Password dependency must be optional. Recommend a layered config: (1) explicit env vars, (2) `pydantic-settings` reading `.env`/keychain, (3) optional `op` wrapper for power users. The current design makes 1Password mandatory, which alienates ~all external users.
* `api_key="not-needed"` for local MLX is fine, but the fallback chain `f"{prefix}_API_KEY" → "OMLX_API_KEY" → "not-needed"` should be documented.

**Verdict**: The zero-plaintext goal is achievable and partially met for *your* environment, but it is currently the #1 portability blocker. Decouple secret-loading from the app via `pydantic-settings` + an optional `op`-wrapper script.

---

## 5. Performance Notes

* **SOP re-parsing** (3.2) — load once.
* **Opik flush on every invocation** — `opik.flush_tracker()` adds latency to every commit; consider making tracing opt-in (`GIT_CG_TRACE=1`) for end users so the hot path is lean. ~1 minute generation time is dominated by the model, but networked tracing flushes add tail latency and a hard dependency on Opik connectivity.
* **rtk routing** (3.6) — currently never fires for normal commits; if compression genuinely helps TTFT, route earlier with a smaller threshold and benchmark.
* **`max_retries=2`** on Instructor is reasonable; each retry re-runs the model (expensive locally). Consider logging when retries fire to know how often the matrix validator forces a re-gen.
* Model selection via `client.models.list()[0]` is a reasonable default but non-deterministic if the server serves multiple models. Pin via config.

---

## 6. TODO.md Prioritisation Audit

### 6.1 Critical tasks you missed (add these to High Priority)
* **[NEW] Purge the leaked AgentOps key from git history + rotate it** (blocking; see 2.1).
* **[NEW] Fix SOP path resolution to be install-relative, not cwd-relative** (blocking for use in any repo other than git-cg's own; see 2.3). This must precede the config-file work — it's the root cause.
* **[NEW] Handle `commit_source` (skip merge/squash/amend)** (correctness bug; see 3.10).
* **[NEW] `.gitignore` the repomix artifact + automate generation** (you list automation under Low — the *gitignore* part is High because of the embedded secret).
* **[NEW] Deduplicate the two release engines** (Python vs Node `.mjs`) before building "release automation," or you'll automate the wrong one (see 3.4).
* **[NEW] Remove dead/legacy artifacts**: `print("IT WORKED!")`, root `commit` file, `main.py` (the placeholder "Hello from gitcommitgenerator!" at repo root is not the entrypoint — the real one is `src/git_cg/main.py`), and the legacy zsh/usage specs (`usage.kdl`, `scripts/generate_ai_commit.zsh.usage.kdl`, `bin/git-cg` wrapper) that reference a `generate_ai_commit.zsh` that no longer exists. These actively mislead.

### 6.2 Architectural refactors to prioritise BEFORE feature expansion
1. **SOP path resolution + config system (`pydantic-settings`)** — unblocks portability, model selection, spelling variants, exclusions, and the Australian-English feature in one stroke. Do this first.
2. **Engine registry/strategy pattern** — unblocks "other AI backends" cleanly (see 3.9).
3. **Single release engine** — unblocks SemVer/changelog/release automation without divergence.
4. **Deterministic test harness with a fixed golden diff** — your own High-Priority item is correct and should gate everything else; without it you can't measure whether refactors regress quality.

### 6.3 Per-item commentary on your TODO

**High Priority — agree with all; notes:**
* *Secret scan / GitLeaks-TruffleHog-BetterLeaks*: Yes, but the scan **will find the AgentOps key in history**. Add `gitleaks` as a pre-commit hook via `hk` and run `gitleaks detect` over history. TruffleHog has better history+verification; GitLeaks is faster for the pre-commit gate. Use both (GitLeaks gate + TruffleHog history audit).
* *Portability/config*: Correct, but reframe as "decouple 1Password + SOP path" (see 2.3, 4).
* *`pydantic-settings` + `SecretStr` + env tiers*: Strongly agree — this is the keystone. The dev/staging/prod tiers are overkill for a local CLI; collapse to a single `Settings` with sensible env overrides. The `conftest.py` override pattern is good.
* *hk integration / fix hooks*: Already largely done (`hk.pkl` works per handoff). Mark in-progress, not TODO.
* *Requirements check / flesh out mise.toml*: Agree. `mlx` is **not** an installable mise tool in the way listed — MLX is a pip/uv Python package and the inference *servers* (oMLX/MTPLX) come via Brew. Correct the inventory: mise handles python/node/uv/hk/pkl/usage/just/rtk; Brewfile handles oMLX/MTPLX; uv handles python deps. Don't promise `mise install mlx`.
* *Confirm dialog before commit*: Agree — but note hooks run non-interactively in many flows; gate it on a TTY check.
* *Repeatable testing/eval*: This is the most important non-blocking item. Concrete proposal in §7.
* *CI/CD + Snyk/Sentry*: Agree on CI (GitHub Actions: ruff, tests, gitleaks). Snyk/Sentry are heavy for a local CLI; Sentry only if you ship telemetry (which conflicts with the privacy-first/local-first ethos — keep opt-in). Prefer Dependabot/`uv lock` audit + gitleaks over Snyk initially.
* *MTPLX license/attribution cascade*: You do **not** need to recursively attribute transitive deps. Reproduce MTPLX's own LICENSE/NOTICE and cite it; transitive attribution is the responsibility of MTPLX's NOTICE file. A `NOTICES.md` aggregating direct deps' licenses (you already have the table) is sufficient for MIT/Apache-2.0 compliance. Apache-2.0 specifically requires you to retain their NOTICE if present.

**Medium Priority — notes:**
* *Migrate instructor → PydanticAI*: **Defer.** Instructor is doing exactly what you need (structured extraction + retry). PydanticAI is an agent framework; migrating buys you multi-step tool use you don't currently need and costs a major refactor. Revisit only if release-note generation becomes genuinely agentic (multi-tool). Your instinct to "carefully consider" is right — my recommendation is *don't*, yet.
* *Model selection / other backends*: Gate behind the engine-registry refactor (6.2.2).
* *Speed-optimised small models (Phi-3.5, Qwen3-3B, Gemma)*: Good experiment, but **measure with the golden-diff harness first** — a 4B model that's fast but picks the wrong gitmoji fails your own "speed isn't everything" test. The matrix validator + retry will mask some small-model errors but at a latency cost.
* *MCP server*: Reasonable, niche. Low-medium.
* *HF token / provider token storage / model dir config*: All good config-system items — fold into the `pydantic-settings` work. **Security note**: don't recommend storing raw tokens at `~/.git/github-token` etc. in plaintext; prefer the OS keychain or the existing `op` path, with plaintext files as a documented last resort with `chmod 600`.
* *Release-note generation*: Good feature; design it to reuse the changelog grouping you already have, and make it pluggable as you suggest.

**Low Priority — notes:**
* *TODO/README roadmap mirroring*: Recommend **single source** — keep `TODO.md` canonical, generate a trimmed roadmap section into README via a `just` task. Don't gitignore TODO.md; it's useful provenance.
* *Static site / zensical / DeepWiki / llms.txt*: Fine once the tool is public-ready. DeepWiki badge is cheap and nice.
* *Australian English enforcement*: Good optional feature. **Don't use `TZ`** for this (you already flagged the confusion) — use explicit `GIT_CG_SPELLING=en_AU`. Implement as a post-generation lint (a small en-US→en-AU word map) rather than relying on the model, which is more deterministic than prompt-only enforcement.
* *Completions (bash/fish/zsh)*: Easy win; Typer can generate these natively (you currently disabled completion with `add_completion=False`). Note: the `usage`-based completion path is legacy (tied to the dead zsh script). Re-enable Typer completion instead.
* *JJ (Jujutsu) support*: Niche but elegant; low priority is right.
* *Benchmark oMLX/MTPLX/vLLM/etc.*: Valuable for README credibility; depends on the harness.
* *gguf exploration*: Correctly flagged as conflicting with MTP heads — keep low.

**"Do Not Implement" — agree, with one caveat:**
* The embedding/DB "learn from history" idea is correctly parked. It risks hallucination/plagiarism of prior commits and adds an always-on process. **However**, a *much* lighter version — caching the last-N commit subjects as few-shot examples in the prompt — could improve consistency cheaply without a DB. Consider that as a Medium item instead of the full vector-DB approach.
* The Polars/StructLog/Loguru/Rich/Ruff/Textual list: you already use Rich and Ruff. For a CLI this size, **Loguru or structlog** (pick one) for `--verbose` logging is a reasonable small win; the rest (Polars, DuckDB, SQLModel) are unjustified for current scope.

---

## 7. Recommended Eval/Test Harness (fleshing out your High-Priority item)

You correctly identified that speed alone is a bad metric. Concrete design:

* **Golden corpus**: store N fixed diffs as fixtures (`tests/fixtures/diffs/*.diff`) covering each commit class (feat, fix, refactor, breaking, docs, multi-file, huge-diff, binary, rename). Pin them so results are comparable run-to-run.
* **Deterministic generation**: set `temperature=0`, fixed seed where the engine supports it, for the eval runs (separate from production sampling).
* **Objective metrics** (cheap, automatable):
  * Schema validity (Pydantic parse pass/fail) — binary.
  * Matrix compliance (emoji↔cc_type correct per SOP) — binary, you already validate this.
  * Header ≤72 chars — binary.
  * Imperative-mood heuristic / no-trailing-period — regex.
  * Scope present when diff touches a single module — heuristic.
* **Subjective metric**: use the Opik `llm_as_judge` rule you already scaffolded (`setup_opik_eval_rule.py`) for accuracy ("does the message reflect the diff?"), scored 0/1 with rationale. Aggregate to a quality score.
* **Composite report**: emit `(model, quality_score, latency_p50, latency_p95, retry_rate)` per run so you can trade off speed vs. quality explicitly — directly answering your "1s-wrong vs 15s-right" concern.
* This harness must land before the model-shootout TODOs, or the shootout is just vibes.

---

## 8. Prompt-Engineering Suggestions

* **Inject the SOP as a tool/structured context, not a giant JSON blob.** You currently `json.dumps` the full 75-row matrix + specs + workflow into the system prompt. That's a large, noisy prompt for a small local model and inflates latency. Options: (a) pre-filter the matrix to the most likely candidates based on changed file types/heuristics; (b) collapse the matrix to a compact `emoji=cc_type` lookup table (you already enforce correctness in Pydantic, so the model only needs enough to pick *intent*); (c) move the verbose workflow phases out of the per-call prompt.
* **Few-shot beats specification for small models.** Add 2–3 worked diff→commit examples (the model copies format better from examples than from rules). Pull them from the SOP example field you already have.
* **The 72-char constraint is stated twice** (system prompt + field description). Good, but small models still violate it — add a deterministic post-render truncation/validation guard (the Node gatekeeper catches it at commit-msg, but the Python side should self-heal first). Consider a `@field_validator` that hard-caps the rendered header and forces a retry with the measured overflow fed back.
* **Multi-line/multi-change support** (your TODO): structure this as an optional `changes: list[ChangeLine]` field in the Pydantic model that renders as body bullet points, rather than free-text body. This makes it deterministic and parseable.

---

## 9. Quick-Win Cleanup Checklist

- [ ] Rotate AgentOps key; purge from history; gitignore + regenerate repomix.
- [ ] Make SOP path install-relative (`importlib.resources`).
- [ ] Handle `commit_source` (skip merge/squash/amend).
- [ ] Delete dead code: root `main.py`, `commit` file, `print("IT WORKED!")`, legacy zsh/usage specs, `bin/git-cg` wrapper.
- [ ] Reconcile versions (pyproject 0.1.7 / package.json 1.0.0 / mise py3.14 vs pyproject py3.12).
- [ ] Pick one release engine (recommend Python; remove `cut_release.mjs` or demote).
- [ ] Stop file I/O inside the Pydantic validator; cache SOP once.
- [ ] Don't swallow SOP-load failures silently.
- [ ] Add `gitleaks` to the hk pre-commit hook.
- [ ] Re-enable Typer completions; drop usage-based legacy path.

---

## 10. What's Genuinely Good (keep)

* The Instructor + Pydantic structured-extraction core with self-healing retries.
* The dual-gate validation (Pydantic at generation, Node at `commit-msg`) — defence in depth.
* The machine-readable SOP as the single source of the gitmoji↔cc_type↔semver↔changelog mapping, with a JSON Schema. This is the project's best idea.
* The hk/mise/just/uv toolchain choice is coherent and modern.
* The Opik tracing + `llm_as_judge` scaffold gives you a real path to objective eval.
* The local-first Apple Silicon focus (oMLX/MTPLX) is a genuine differentiator vs. cloud commit tools.
