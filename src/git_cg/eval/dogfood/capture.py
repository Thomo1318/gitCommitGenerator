"""S6 Slice 7 dogfood capture engine (R12 / S6-G).

Deterministic, offline-first. Never a product-accept gate. ``authority`` is
always ``advisory`` on every emitted ``dogfood_attachment_v1``.

Mode law (closed):
* ``off``    — capture nothing (default for non-maintainers).
* ``sample`` — deterministic membership from seed+rate over a stable population.
* ``always`` — capture every eligible commit.
* ``async``  — capture intent is recorded immediately; judge execution happens
  on a non-blocking seam that the commit path never awaits (S6-G02a).

``capture_on`` (``pass|fail|all``) is owner-set corpus eligibility, separate
from product accept; ``fail`` retains a **hard-negative candidate** on failing
rows without failing the product path, and skips passing rows.

Import law: import-light. Path / schema / pin helpers are lazy.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "dogfood_attachment_v1"

MODE_OFF: Final[str] = "off"
MODE_SAMPLE: Final[str] = "sample"
MODE_ALWAYS: Final[str] = "always"
MODE_ASYNC: Final[str] = "async"

#: Closed mode vocabulary.
DOGFOOD_MODES: Final[frozenset[str]] = frozenset({MODE_OFF, MODE_SAMPLE, MODE_ALWAYS, MODE_ASYNC})

#: Owner-set corpus capture eligibility (separate from product accept).
CAPTURE_ON_VALUES: Final[frozenset[str]] = frozenset({"pass", "fail", "all"})

#: Env knobs (lab/maintainer only; never required on the basic commit path).
ENV_DOGFOOD_MODE: Final[str] = "GIT_CG_EVAL_DOGFOOD_MODE"
ENV_DOGFOOD_SEED: Final[str] = "GIT_CG_EVAL_DOGFOOD_SEED"
ENV_DOGFOOD_RATE: Final[str] = "GIT_CG_EVAL_DOGFOOD_RATE"

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_MAINTAINER_PROFILES: Final[frozenset[str]] = frozenset({"maintainer", "train", "dogfood"})


class DOGFoodError(ValueError):
    """Deterministic dogfood failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dogfood_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, dogfood_dir

    try:
        return dogfood_dir(repo)
    except LayerAPathError as exc:
        raise DOGFoodError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise DOGFoodError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def is_maintainer_profile(env: Mapping[str, str] | None = None) -> bool:
    """True only for maintainer-class profiles; default is **not** maintainer."""
    source = os.environ if env is None else env
    profile = (source.get("GIT_CG_EVAL_PROFILE") or "").strip().lower()
    return profile in _MAINTAINER_PROFILES


def resolve_dogfood_mode(
    *,
    mode: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve the effective dogfood mode (closed set; fail-closed to ``off``).

    Precedence: explicit ``--mode`` > ``GIT_CG_EVAL_DOGFOOD_MODE`` > default.
    Non-maintainer default is ``off`` (S6-G01); maintainer default is
    ``async``+advisory while building (R12 owner lock).
    """
    source = os.environ if env is None else env
    token = mode if mode is not None else source.get(ENV_DOGFOOD_MODE)
    if token is not None:
        cleaned = str(token).strip().lower()
        if cleaned in DOGFOOD_MODES:
            return cleaned
        raise DOGFoodError(
            f"invalid dogfood mode: {token!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {'|'.join(sorted(DOGFOOD_MODES))}",
        )
    return MODE_ASYNC if is_maintainer_profile(source) else MODE_OFF


def derive_sample_seed(
    *,
    explicit_seed: str | None = None,
    experiment_or_run_id: str | None = None,
    suite_id: str | None = None,
    rate: float,
) -> str:
    """Deterministic sample seed: explicit ``--seed`` wins; else stable hash.

    Stable hash input is ``(experiment_id|run_id, suite_id, rate)`` — never
    wall-clock (S6-G08). The returned seed is a 64-hex SHA-256 string.
    """
    if explicit_seed is not None:
        cleaned = str(explicit_seed).strip()
        if not cleaned:
            raise DOGFoodError("--seed must be a non-empty string", code="EVAL_USAGE", exit_code=2)
        return cleaned
    pop = f"{experiment_or_run_id or 'run'}|{suite_id or 'suite'}|{rate:.6f}"
    return hashlib.sha256(pop.encode("utf-8")).hexdigest()


def _canonical_selected_hash(selected: Iterable[str]) -> str:
    canon = json.dumps(sorted(str(s) for s in selected), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def select_sample_members(
    population: Iterable[str],
    *,
    rate: float,
    seed: str,
) -> list[str]:
    """Deterministic membership: stable hash order, first ``ceil(rate*N)`` members.

    No wall-clock, no RNG state — membership is a pure function of
    ``(population, rate, seed)`` and is offline-reproducible from the
    attachment alone.
    """
    members = sorted({str(m) for m in population if str(m).strip()})
    if not members:
        return []
    if not (0.0 <= rate <= 1.0):
        raise DOGFoodError(f"sample rate must be in [0,1]: {rate!r}", code="EVAL_USAGE", exit_code=2)
    n = round(rate * len(members))
    if n <= 0:
        return []
    if n >= len(members):
        return members

    def _key(member: str) -> str:
        return hashlib.sha256(f"{seed}|{member}".encode()).hexdigest()

    ordered = sorted(members, key=_key)
    return ordered[:n]


def attachment_reproduces_membership(attachment: Mapping[str, Any]) -> bool:
    """Verify a sample attachment reproduces its own selected set offline.

    Preferred path (S6-G08): resample from recorded ``population_members`` using
    ``sample_seed`` + ``sample_rate``, then compare selected ids and/or hash.
    Fallback: when population members are absent, verify that any recorded
    ``selected_ids`` match ``selected_set_hash`` (hash-only consistency).
    """
    if attachment.get("mode") != MODE_SAMPLE:
        return True
    seed = str(attachment.get("sample_seed") or "")
    rate = attachment.get("sample_rate")
    if not seed or not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return False
    selected = [str(s) for s in (attachment.get("selected_ids") or [])]
    claimed_hash = str(attachment.get("selected_set_hash") or "")
    population = [str(m) for m in (attachment.get("population_members") or []) if str(m).strip()]
    if population:
        try:
            resampled = select_sample_members(population, rate=float(rate), seed=seed)
        except DOGFoodError:
            return False
        # Membership is set-valued; attachments may store selected_ids sorted.
        if selected and set(resampled) != set(selected):
            return False
        # rate=0 is a valid empty draw when population was recorded.
        if not claimed_hash:
            return True
        return _canonical_selected_hash(resampled) == claimed_hash
    # Hash-only fallback (legacy attachments without population_members).
    if claimed_hash and selected:
        return _canonical_selected_hash(selected) == claimed_hash
    return False


def build_attachment(
    *,
    message_sha256: str,
    mode: str,
    run_id: str | None = None,
    judge_id: str = "judge-craft-v1",
    metric_id: str | None = None,
    score: float | None = None,
    polarity: str | None = None,
    rationale_short: str | None = None,
    latency_ms: float | None = None,
    case_id: str | None = None,
    bundle_id: str | None = None,
    session_thread_id: str | None = None,
    capture_on: str | None = None,
    hard_negative_candidate: bool = False,
    sample_seed: str | None = None,
    sample_rate: float | None = None,
    population_id: str | None = None,
    population_members: Iterable[str] | None = None,
    selected_ids: Iterable[str] | None = None,
    notes: str | None = None,
    authority: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``dogfood_attachment_v1`` (fail-closed)."""
    if mode not in DOGFOOD_MODES:
        raise DOGFoodError(f"invalid dogfood mode: {mode!r}", code="EVAL_USAGE", exit_code=2)
    if authority is not None and str(authority).strip().lower() != "advisory":
        raise DOGFoodError(
            "dogfood authority is fixed to advisory (never sole gate/golden)",
            code="EVAL_USAGE",
            exit_code=2,
            hint="R12/S6-G03: dogfood attachments cannot carry law/block authority.",
        )
    if capture_on is not None and capture_on not in CAPTURE_ON_VALUES:
        raise DOGFoodError(
            f"invalid capture_on: {capture_on!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Allowed: pass|fail|all",
        )
    if polarity is not None and polarity not in {"higher_is_better", "lower_is_better", "pass_fail"}:
        raise DOGFoodError(f"invalid polarity: {polarity!r}", code="EVAL_USAGE", exit_code=2)

    sha = str(message_sha256).strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise DOGFoodError("message_sha256 must be 64-hex", code="EVAL_USAGE", exit_code=2)

    rid = run_id or f"dog-{uuid.uuid4().hex[:12]}"
    if not _SAFE_ID.fullmatch(rid):
        raise DOGFoodError(f"invalid run_id: {rid!r}", code="EVAL_USAGE", exit_code=2)

    selected = sorted({str(s) for s in (selected_ids or []) if str(s).strip()})

    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    attachment: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": f"{rid}-{judge_id}",
        "run_id": rid,
        "judge_id": judge_id,
        "pin_ref": schema_pack_pin(),
        "mode": mode,
        "authority": "advisory",
        "message_sha256": sha,
        "created_at": _utc_now(),
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if metric_id is not None:
        attachment["metric_id"] = metric_id
    if score is not None:
        attachment["score"] = float(score)
    if polarity is not None:
        attachment["polarity"] = polarity
    if rationale_short is not None:
        attachment["rationale_short"] = str(rationale_short)[:2000]
    if latency_ms is not None:
        attachment["latency_ms"] = float(latency_ms)
    if case_id is not None:
        attachment["case_id"] = case_id
    if bundle_id is not None:
        attachment["bundle_id"] = bundle_id
    if session_thread_id is not None:
        attachment["session_thread_id"] = session_thread_id
    if capture_on is not None:
        attachment["capture_on"] = capture_on
    if hard_negative_candidate:
        attachment["hard_negative_candidate"] = True
    if notes is not None:
        attachment["notes"] = notes

    if mode == MODE_SAMPLE:
        if not sample_seed or sample_rate is None or not population_id:
            raise DOGFoodError(
                "mode=sample requires sample_seed, sample_rate, population_id",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Provide --seed/--rate or let derive_sample_seed compute a stable seed.",
            )
        pop_members = sorted({str(m) for m in (population_members or []) if str(m).strip()})
        attachment["sample_seed"] = str(sample_seed)
        attachment["sample_rate"] = float(sample_rate)
        attachment["population_id"] = str(population_id)
        if pop_members:
            attachment["population_members"] = pop_members
        if selected:
            attachment["selected_ids"] = selected
            attachment["selected_set_hash"] = _canonical_selected_hash(selected)
        elif pop_members:
            # Derive selected set when only population is supplied.
            selected = select_sample_members(pop_members, rate=float(sample_rate), seed=str(sample_seed))
            if selected:
                attachment["selected_ids"] = selected
                attachment["selected_set_hash"] = _canonical_selected_hash(selected)

    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_VERSION, attachment)
    except SchemaPackError as exc:
        raise DOGFoodError(
            f"dogfood_attachment_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    return attachment


def write_attachment(repo: Path, attachment: dict[str, Any]) -> Path:
    """Persist a validated attachment under ``.eval/dogfood/`` (atomic, contained)."""
    aid = str(attachment.get("id") or "")
    if not _SAFE_ID.fullmatch(aid):
        raise DOGFoodError(f"invalid attachment id: {aid!r}", code="EVAL_USAGE", exit_code=2)
    path = _dogfood_dir(repo) / f"{aid}.json"
    cleaned = {k: v for k, v in attachment.items() if v is not None}
    return _atomic_write(path, cleaned)


def capture_dogfood(
    repo: Path,
    *,
    message_sha256: str,
    mode: str | None = None,
    capture_on: str = "all",
    deterministic_pass: bool | None = None,
    seed: str | None = None,
    rate: float | None = None,
    population: Iterable[str] | None = None,
    suite_id: str | None = None,
    run_id: str | None = None,
    case_id: str | None = None,
    bundle_id: str | None = None,
    session_thread_id: str | None = None,
    score: float | None = None,
    metric_id: str | None = None,
    polarity: str | None = None,
    rationale_short: str | None = None,
    latency_ms: float | None = None,
    judge_id: str = "judge-craft-v1",
    notes: str | None = None,
    write: bool = True,
    env: Mapping[str, str] | None = None,
    judge_runner: Any | None = None,
) -> dict[str, Any]:
    """Capture one dogfood attachment (or report skip). Never blocks product.

    Returns a CLI data payload with ``captured``/``skipped`` + attachment.

    S6-G02(a): when ``mode=async``, this seam records capture intent only and
    **never** invokes ``judge_runner`` (if supplied). A blocking/sync judge is
    therefore unreachable from the async commit-adjacent path.
    """
    source = os.environ if env is None else env
    if capture_on not in CAPTURE_ON_VALUES:
        raise DOGFoodError(
            f"invalid capture_on: {capture_on!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Allowed: pass|fail|all",
        )
    resolved_mode = resolve_dogfood_mode(mode=mode, env=source)
    if resolved_mode == MODE_OFF:
        return {
            "captured": False,
            "skipped": True,
            "mode": resolved_mode,
            "reason": "dogfood_off",
            "authority": "advisory",
            "product_block": False,
            "async_never_awaits_judge": False,
            "judge_invoked": False,
        }

    # Env knobs (lab only): explicit args win; else GIT_CG_EVAL_DOGFOOD_*.
    effective_seed = seed
    if effective_seed is None:
        env_seed = source.get(ENV_DOGFOOD_SEED)
        if env_seed is not None and str(env_seed).strip():
            effective_seed = str(env_seed).strip()

    if rate is not None:
        effective_rate = float(rate)
    else:
        env_rate = source.get(ENV_DOGFOOD_RATE)
        if env_rate is not None and str(env_rate).strip():
            try:
                effective_rate = float(str(env_rate).strip())
            except ValueError as exc:
                raise DOGFoodError(
                    f"invalid {ENV_DOGFOOD_RATE}: {env_rate!r}",
                    code="EVAL_USAGE",
                    exit_code=2,
                ) from exc
        else:
            effective_rate = 1.0

    pop: list[str] = []
    if resolved_mode == MODE_SAMPLE:
        pop = sorted({str(p) for p in (population or []) if str(p).strip()})
        if not pop:
            return {
                "captured": False,
                "skipped": True,
                "mode": resolved_mode,
                "reason": "empty_population",
                "authority": "advisory",
                "product_block": False,
                "async_never_awaits_judge": False,
                "judge_invoked": False,
            }
        sample_seed = derive_sample_seed(
            explicit_seed=effective_seed,
            experiment_or_run_id=run_id,
            suite_id=suite_id,
            rate=effective_rate,
        )
        selected = select_sample_members(pop, rate=effective_rate, seed=sample_seed)
        population_id = f"{suite_id or 'suite'}:{len(pop)}"
    else:
        sample_seed = None
        selected = []
        population_id = None

    # capture_on eligibility (corpus-only; never a product fail).
    hard_negative = False
    if capture_on == "pass" and deterministic_pass is False:
        return {
            "captured": False,
            "skipped": True,
            "mode": resolved_mode,
            "reason": "capture_on=pass skips failing rows",
            "authority": "advisory",
            "product_block": False,
            "async_never_awaits_judge": resolved_mode == MODE_ASYNC,
            "judge_invoked": False,
        }
    if capture_on == "fail" and deterministic_pass is True:
        return {
            "captured": False,
            "skipped": True,
            "mode": resolved_mode,
            "reason": "capture_on=fail skips passing rows",
            "authority": "advisory",
            "product_block": False,
            "async_never_awaits_judge": resolved_mode == MODE_ASYNC,
            "judge_invoked": False,
        }
    if deterministic_pass is False and capture_on in {"fail", "all"}:
        # Hard-negative candidate retained WITHOUT failing product accept.
        hard_negative = True

    # S6-G02(a) structural seam: async never invokes/awaits the judge runner.
    judge_invoked = False
    judge_score = score
    judge_latency = latency_ms
    judge_rationale = rationale_short
    if resolved_mode != MODE_ASYNC and callable(judge_runner):
        outcome = judge_runner()
        judge_invoked = True
        if isinstance(outcome, Mapping):
            if "score" in outcome and judge_score is None:
                judge_score = outcome.get("score")  # type: ignore[assignment]
            if "latency_ms" in outcome and judge_latency is None:
                judge_latency = outcome.get("latency_ms")  # type: ignore[assignment]
            if "rationale_short" in outcome and judge_rationale is None:
                judge_rationale = outcome.get("rationale_short")  # type: ignore[assignment]

    attachment = build_attachment(
        message_sha256=message_sha256,
        mode=resolved_mode,
        run_id=run_id,
        judge_id=judge_id,
        metric_id=metric_id,
        score=judge_score,
        polarity=polarity,
        rationale_short=judge_rationale,
        latency_ms=judge_latency,
        case_id=case_id,
        bundle_id=bundle_id,
        session_thread_id=session_thread_id,
        capture_on=capture_on,
        hard_negative_candidate=hard_negative,
        sample_seed=sample_seed,
        sample_rate=effective_rate if resolved_mode == MODE_SAMPLE else None,
        population_id=population_id,
        population_members=pop if resolved_mode == MODE_SAMPLE else None,
        selected_ids=selected,
        notes=notes,
    )
    path = write_attachment(repo, attachment) if write else None
    return {
        "captured": True,
        "skipped": False,
        "mode": resolved_mode,
        "attachment": attachment,
        "attachment_id": attachment["id"],
        "path": path.as_posix() if path is not None else None,
        "hard_negative_candidate": hard_negative,
        "sample_selected": len(selected) if resolved_mode == MODE_SAMPLE else None,
        "authority": "advisory",
        "product_block": False,
        "async_never_awaits_judge": resolved_mode == MODE_ASYNC,
        "judge_invoked": judge_invoked,
    }


__all__ = [
    "CAPTURE_ON_VALUES",
    "DOGFOOD_MODES",
    "ENV_DOGFOOD_MODE",
    "ENV_DOGFOOD_RATE",
    "ENV_DOGFOOD_SEED",
    "MODE_ALWAYS",
    "MODE_ASYNC",
    "MODE_OFF",
    "MODE_SAMPLE",
    "SCHEMA_VERSION",
    "DOGFoodError",
    "attachment_reproduces_membership",
    "build_attachment",
    "capture_dogfood",
    "derive_sample_seed",
    "is_maintainer_profile",
    "resolve_dogfood_mode",
    "select_sample_members",
    "write_attachment",
]
