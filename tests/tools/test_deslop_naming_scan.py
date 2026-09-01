"""Unit tests for tools/deslop_naming_scan.py (stdin fixtures; no git required)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "deslop_naming_scan.py"


def _load():
    spec = importlib.util.spec_from_file_location("deslop_naming_scan", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Python 3.14 dataclasses look up cls.__module__ in sys.modules during
    # @dataclass processing; register before exec_module.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def _run_stdin(path_label: str, content: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--stdin-file",
            "--path",
            path_label,
            "--format",
            "json",
        ],
        input=content,
        text=True,
        capture_output=True,
        cwd=REPO,
        check=False,
    )


def test_flags_stage_recipe_and_artifact():
    content = """
eval-s7-proof:
    @echo gate

eval-s15-coverage-files:
    @rm -f .eval/s15_per_file_coverage.json
"""
    proc = _run_stdin("justfile", content)
    assert proc.returncode == 2, proc.stderr
    assert "eval-s7-proof" in proc.stdout
    assert "s15_per_file_coverage.json" in proc.stdout or "s15" in proc.stdout


def test_flags_finding_and_governance_identity_symbols():
    content = """
def handle_finding_6(data):
    return data

def apply_d31_gate():
    return None

def test_find_003_regression():
    assert True

def nth03_export():
    return {}

def p0_fix_path():
    return "x"

def handle_e07():
    return None

def e07_gate():
    return None

def run_error_e07():
    return None

def s6_g02_bench():
    return None

def s7_dog_05_case():
    return None
"""
    proc = _run_stdin("src/git_cg/example.py", content)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    out = proc.stdout
    assert "finding_6" in out or "handle_finding_6" in out
    assert "apply_d31_gate" in out or "d31_gate" in out
    assert "find_003" in out or "test_find_003" in out
    assert "nth03" in out
    assert "p0_fix" in out
    assert "handle_e07" in out or "e07_gate" in out
    assert "run_error_e07" in out or "error_e07" in out
    assert "s6_g02" in out or "s7_dog_05" in out


def test_preserves_bare_citations_in_comments_and_tables():
    content = '''
# D26: scrub presentation locals; closed tags only.
# FIND-068 product-path Opik stays lazy.
# E07: invalid mode → config_error (matrix cite only).
| D31 | Decision text |
| E13 | Offline matrix minimum |
| E12 | Invalid mode config_error |
| F-S6-04 | Failure row |
| F12 | Failure taxonomy |
| NTH-03 | Nice to have |
| P0 | Priority |
| P2-8 | Work package cite |
| S6-G02 | Claim coordinate |
| S6-A04 | Acceptance coordinate |
| S7-DOG-05 | Dogfood coordinate |
| FIND-032 | S7 run status naming (S7-DOG-04) |

def scrub_presentation_locals():
    """Keep domain name; citation only in comment above."""
    return None

def invalid_mode_config_error():
    """Domain failure name — not an E-token identity."""
    return None
'''
    proc = _run_stdin("src/git_cg/ok.py", content)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_preserves_docstring_and_plan_matrix_citations():
    content = '''
"""Tier-1 Feedback Definition vocabulary map (S7-2)."""

# Per-lane project-pin provenance (S7-1a; observability, never BLOCK).

| FIND-033 | S7 session interaction dogfood (S7-DOG-05) |
| S6-G02 | Measurement row |

See decision D31 and risk RK-S6-02 for context.
E07 and E13 remain matrix citations; S6-G02 is a claim row.
'''
    proc = _run_stdin("docs/plans/opik-evaluation-harness.md", content)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_markdown_plan_noise_vs_operator_teaching():
    noise = """
## Refinement: S7/S8 harness scope clarification
| FIND-033 | S7 session (S7-DOG-05) |
See scratch/s7-batch-h/evidence/h62_promote_valid.json and R13/S6.
Plan SSOT @ `0.9.8-s7-dogfood-findings-board`
"""
    proc = _run_stdin("docs/plans/opik-evaluation-harness.md", noise)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    taught = """
Run `just eval-s7-proof` and inspect `.eval/s7_per_file_coverage.json`.
"""
    proc = _run_stdin("docs/eval/README.md", taught)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "eval-s7-proof" in proc.stdout


def test_domain_first_names_clean():
    content = """
eval-package-coverage:
    @echo package coverage

eval-per-file-coverage:
    @rm -f .eval/per_file_coverage.json

def sanitize_commit_trailer(value: str) -> str:
    return value

def test_rejects_malformed_trailer_prefix():
    assert True
"""
    proc = _run_stdin("justfile", content)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_docs_operator_backticks_flag_stage_recipe():
    content = """
Run `just eval-s8-proof` then open `.eval/s8_per_file_coverage.json`.
"""
    proc = _run_stdin("docs/eval/README.md", content)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "eval-s8-proof" in proc.stdout


def test_scan_lines_api_families():
    mod = _load()
    findings = mod.scan_lines(
        "tools/x.py",
        [
            (1, "def run_slice_12_handler():"),
            (2, "    path = 'rk_s6_02_flag'"),
            (3, "    return path"),
        ],
    )
    families = {f.family for f in findings}
    tokens = {f.token for f in findings}
    assert any(x.startswith("A.") for x in families) or "slice_12_handler" in tokens
    assert any("rk" in t.lower() for t in tokens) or any(x.startswith("C.RK") for x in families)


def test_flags_error_evidence_identity_shapes():
    """Family C Errors: E<N> as durable identity, not matrix citation."""
    content = """
def handle_e07():
    return None

def e07_gate():
    return None

def run_error_e07():
    return None

def test_e12_schema_only():
    assert True
"""
    proc = _run_stdin("src/git_cg/eval/error_ids.py", content)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    out = proc.stdout.lower()
    assert "handle_e07" in out or "e07_gate" in out
    assert "run_error_e07" in out or "error_e07" in out
    assert "test_e12" in out or "e12_schema" in out


def test_flags_claim_matrix_coordinate_identity():
    content = """
def s6_g02_bench():
    return None

def s7_dog_05_case():
    return None

def s6_a04_metric():
    return None

def p2_8_runner():
    return None
"""
    proc = _run_stdin("src/git_cg/eval/claim_ids.py", content)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    out = proc.stdout
    assert "s6_g02" in out
    assert "s7_dog_05" in out or "dog_05" in out
    assert "s6_a04" in out
    assert "p2_8" in out


def test_preserves_domain_error_names_without_e_token():
    content = """
def invalid_mode_config_error():
    return None

def emit_config_error_for_unknown_mode():
    return None

class ErrorCode:
    INVALID_MODE = "invalid_mode"
"""
    proc = _run_stdin("src/git_cg/eval/domain_errors.py", content)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_scan_lines_error_and_claim_families():
    mod = _load()
    findings = mod.scan_lines(
        "tools/x.py",
        [
            (1, "def handle_e07():"),
            (2, "    path = 'e07_gate'"),
            (3, "    other = 's6_g02_bench'"),
            (4, "    return path"),
        ],
    )
    families = {f.family for f in findings}
    tokens = {f.token for f in findings}
    assert any(x.startswith("C.E") for x in families) or "handle_e07" in tokens
    assert "s6_g02_bench" in tokens or any(x.startswith("C.S") for x in families)
