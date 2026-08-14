"""Family B — Hybrid format wraps via product parse law."""

from __future__ import annotations

from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.product_bridges import (
    extract_trailers,
    issue_ref_ok,
    known_cc_type,
    known_semver,
    parse_hybrid_header,
    parse_message_to_plan,
)
from git_cg.eval.scoring.result_builder import make_score

FAMILY_B_S2A = (
    "b.header_shape",
    "b.gitmoji_present",
    "b.cc_type_known",
    "b.scope_shape",
    "b.subject_length",
    "b.trailers_parse",
    "b.trailers_issue_ref",
    "b.trailers_semver",
    "b.trailers_change_types",
    "b.trailers_changelog_groups",
    "b.structured_envelope",
)

_PA = "git_cg.telemetry.reverse_parse_commit_message+hybrid_header"


def score_family_b(ctx: ScoreContext) -> list[ScoreResultV1]:
    """
    Score a Family B hybrid commit message against its required format and metadata.
    
    Parameters:
    	ctx (ScoreContext): Context containing the final commit message to score.
    
    Returns:
    	list[ScoreResultV1]: Scores covering the hybrid header, trailers, issue references, and structured commit envelope.
    """
    msg = ctx.final_message or ""
    header = parse_hybrid_header(msg)
    trailers = extract_trailers(msg)
    scores: list[ScoreResultV1] = []

    shape_ok = bool(header.get("ok"))
    scores.append(
        make_score(
            "b.header_shape",
            shape_ok,
            reason=None if shape_ok else header.get("reason") or "header_shape_mismatch",
            evidence={"header": header.get("header"), "header_len": header.get("header_len")},
            failure_ids=None if shape_ok else ["HYBRID_HEADER_SHAPE"],
            product_authority=_PA,
        )
    )

    gitmoji = str(header.get("gitmoji") or "")
    gitmoji_ok = bool(gitmoji.strip())
    scores.append(
        make_score(
            "b.gitmoji_present",
            gitmoji_ok,
            reason=None if gitmoji_ok else "gitmoji_missing",
            evidence={"gitmoji": gitmoji},
            failure_ids=None if gitmoji_ok else ["HYBRID_GITMOJI"],
            product_authority=_PA,
        )
    )

    cc = str(header.get("cc_type") or "")
    cc_ok = known_cc_type(cc)
    scores.append(
        make_score(
            "b.cc_type_known",
            cc_ok,
            reason=None if cc_ok else "cc_type_unknown",
            evidence={"cc_type": cc},
            failure_ids=None if cc_ok else ["HYBRID_CC_TYPE"],
            product_authority="git_cg.models.CommitType",
        )
    )

    scope = header.get("scope")
    if scope is None or scope == "":
        scope_ok = True
    else:
        scope_ok = bool(str(scope).strip()) and all(c.isalnum() or c in "-_," for c in str(scope).replace(" ", ""))
    scores.append(
        make_score(
            "b.scope_shape",
            scope_ok,
            reason=None if scope_ok else "scope_illegal",
            evidence={"scope": scope},
            failure_ids=None if scope_ok else ["HYBRID_SCOPE"],
            product_authority=_PA,
        )
    )

    header_len = int(header.get("header_len") or (len(msg.splitlines()[0]) if msg else 0))
    subj_ok = 0 < header_len <= 72
    scores.append(
        make_score(
            "b.subject_length",
            subj_ok,
            reason=None if subj_ok else "subject_line_exceeds_72",
            evidence={"header_len": header_len},
            failure_ids=None if subj_ok else ["HYBRID_SUBJECT_LEN"],
            product_authority="git_cg.telemetry.run_deterministic_checks",
        )
    )

    has_semver = "SemVer-Impact" in trailers
    has_types = "Change-Types" in trailers
    has_groups = "Changelog-Groups" in trailers
    parse_ok = has_semver and has_types and has_groups
    scores.append(
        make_score(
            "b.trailers_parse",
            parse_ok,
            reason=None if parse_ok else "required_trailers_missing",
            evidence={"trailers": trailers},
            failure_ids=None if parse_ok else ["HYBRID_TRAILER_PARSE"],
            product_authority=_PA,
        )
    )

    iref_ok, iref_reason = issue_ref_ok(trailers)
    scores.append(
        make_score(
            "b.trailers_issue_ref",
            iref_ok,
            reason=iref_reason,
            evidence={
                "issue_trailers": {
                    k: trailers[k] for k in trailers if k in {"Refs", "Resolves", "Closes", "Fixes", "Null"}
                }
            },
            failure_ids=None if iref_ok else ["HYBRID_ISSUE_REF"],
            product_authority="git_cg.models.IssueReference",
        )
    )

    sem_val = trailers.get("SemVer-Impact")
    sem_ok = has_semver and known_semver(sem_val)
    scores.append(
        make_score(
            "b.trailers_semver",
            sem_ok,
            reason=None if sem_ok else "semver_trailer_invalid",
            evidence={"SemVer-Impact": sem_val},
            failure_ids=None if sem_ok else ["HYBRID_SEMVER_TRAILER"],
            product_authority="git_cg.models.SemVerImpact",
        )
    )

    types_val = trailers.get("Change-Types", "")
    types_ok = has_types and bool(types_val.strip())
    scores.append(
        make_score(
            "b.trailers_change_types",
            types_ok,
            reason=None if types_ok else "change_types_missing",
            evidence={"Change-Types": types_val},
            failure_ids=None if types_ok else ["HYBRID_CHANGE_TYPES"],
            product_authority=_PA,
        )
    )

    groups_val = trailers.get("Changelog-Groups", "")
    groups_ok = has_groups and bool(groups_val.strip())
    scores.append(
        make_score(
            "b.trailers_changelog_groups",
            groups_ok,
            reason=None if groups_ok else "changelog_groups_missing",
            evidence={"Changelog-Groups": groups_val},
            failure_ids=None if groups_ok else ["HYBRID_CHANGELOG_GROUPS"],
            product_authority=_PA,
        )
    )

    struct_ok = False
    struct_err = None
    if msg.strip():
        try:
            parse_message_to_plan(msg)
            struct_ok = True
        except Exception as exc:
            struct_err = f"{type(exc).__name__}: {exc}"
    scores.append(
        make_score(
            "b.structured_envelope",
            struct_ok,
            reason=None if struct_ok else struct_err or "structured_envelope_invalid",
            evidence={"error": struct_err} if struct_err else {"ok": True},
            failure_ids=None if struct_ok else ["HYBRID_STRUCT_ENVELOPE"],
            product_authority="git_cg.models.CommitPlan",
        )
    )

    return scores
