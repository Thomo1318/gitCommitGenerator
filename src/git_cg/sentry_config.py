import contextlib
import importlib.metadata
import os

import sentry_sdk


def init_sentry():
    if os.environ.get("GIT_CG_DISABLE_SENTRY", "0") == "1":
        return

    try:
        version = importlib.metadata.version("gitcommitgenerator")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    def scrub_data(event, hint):
        # Prevent massive diffs from overflowing the 8kb context limit or leaking source code
        if "contexts" in event and "git_cg" in event["contexts"] and "diff_output" in event["contexts"]["git_cg"]:
            event["contexts"]["git_cg"]["diff_output"] = "[SCRUBBED]"
        return event

    with contextlib.suppress(Exception):
        sentry_sdk.init(
            dsn=os.environ.get("SENTRY_DSN"),
            environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
            release=f"gitCommitGenerator@{version}",
            send_default_pii=False,
            before_send=scrub_data,
            traces_sample_rate=0.0,
        )
