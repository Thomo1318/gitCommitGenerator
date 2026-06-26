#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

import opik

# Add src to sys.path to allow importing from git_cg
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from git_cg.main import build_system_prompt
from git_cg.telemetry import compute_prompt_hash


def sync_system_prompt(verbose: bool = False):
    """
    Synchronizes the core system instruction prompt used by git-cg to Opik Cloud.

    This is intentionally decoupled from the runtime execution of git-cg to ensure
    zero network latency during local git commits.
    """

    # The base template used in main.py (empty diff_output to avoid language-specific variations)
    system_prompt_base = build_system_prompt(diff_output="")

    prompt_hash = compute_prompt_hash(system_prompt_base)

    if verbose:
        print(f"Computed Prompt Hash: {prompt_hash}")
        print("Synchronizing to Opik Cloud...")

    try:
        opik_client = opik.Opik()

        prompt = opik_client.create_prompt(
            name="git_cg_system_prompt",
            prompt=system_prompt_base,
        )

        if prompt:
            print(f"Successfully synced prompt to Opik Cloud (commit: {prompt.commit}).")
        else:
            print("Failed to sync prompt to Opik Cloud.")
            sys.exit(1)

    except Exception as e:
        print(f"Error during synchronization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync git-cg prompt templates to Opik Cloud.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    args = parser.parse_args()

    sync_system_prompt(verbose=args.verbose)
