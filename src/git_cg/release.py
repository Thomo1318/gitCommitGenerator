import contextlib
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import semver
from rich.console import Console
from rich.panel import Panel

from git_cg.sop import load_sop

console = Console()


def get_sop_data():
    return load_sop()


def get_last_tag() -> str:
    try:
        tag = (
            subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
        return tag
    except subprocess.CalledProcessError:
        return ""


def get_commits_since(tag: str) -> list[str]:
    try:
        if tag:
            log_output = subprocess.check_output(
                ["git", "log", f"{tag}..HEAD", "--pretty=format:%s---COMMIT_BODY---%b---COMMIT_DELIM---"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8")
        else:
            log_output = subprocess.check_output(
                ["git", "log", "--pretty=format:%s---COMMIT_BODY---%b---COMMIT_DELIM---"], stderr=subprocess.DEVNULL
            ).decode("utf-8")

        commits = [line for line in log_output.split("---COMMIT_DELIM---") if line.strip()]
        return commits
    except subprocess.CalledProcessError:
        return []


def get_modified_files_since(tag: str) -> list[str]:
    try:
        # If no tag, get all files currently tracked
        cmd = ["git", "diff", "--name-only", f"{tag}..HEAD"] if tag else ["git", "ls-files"]
        files = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").split("\n")
        return [f for f in files if f.strip() and os.path.exists(f)]
    except subprocess.CalledProcessError:
        return []


def parse_commit_impact(commit_string: str, gitmoji_matrix: list) -> str:
    parts = commit_string.split("---COMMIT_BODY---", 1)
    subject = parts[0]
    body = parts[1] if len(parts) > 1 else ""

    # 1. Prefer machine-readable trailer from CommitPlan
    trailer_match = re.search(r"^SemVer-Impact:\s*(MAJOR|MINOR|PATCH|NONE)", body, flags=re.MULTILINE)
    if trailer_match:
        return trailer_match.group(1).upper()

    # 2. Check for manual breaking change indicators
    if "BREAKING CHANGE:" in body or "BREAKING CHANGE:" in subject:
        return "MAJOR"

    # 3. Legacy fallback: Regex on header cc_type and breaking indicator
    match = re.search(r"^[^\s]+\s+([a-z]+)(?:\(.*?\)?)?(!?):", subject)
    if match:
        cc_type = match.group(1)
        is_breaking = match.group(2) == "!"
        if is_breaking:
            return "MAJOR"

        for entry in gitmoji_matrix:
            if entry.get("cc_type") == cc_type:
                return entry.get("semver_impact", "NONE")

    # 4. Legacy fallback: Check emojis directly
    for entry in gitmoji_matrix:
        if entry.get("emoji") in subject:
            return entry.get("semver_impact", "NONE")

    return "NONE"


def calculate_global_bump(commits: list[str], gitmoji_matrix: list) -> str:
    """
    Determine the highest SemVer bump required by the given commits.

    Parameters:
        commits (list[str]): Commit strings to evaluate.
        gitmoji_matrix (list): Metadata used to interpret commit impact.

    Returns:
        str: "MAJOR", "MINOR", "PATCH", or "NONE", depending on the highest impact found.
    """
    highest_bump = "NONE"
    for commit in commits:
        impact = parse_commit_impact(commit, gitmoji_matrix)
        if impact == "MAJOR":
            return "MAJOR"
        elif impact == "MINOR":
            highest_bump = "MINOR"
        elif impact == "PATCH" and highest_bump == "NONE":
            highest_bump = "PATCH"
    return highest_bump


def bump_version_string(version: str, bump_type: str, pre_release: str | None = None) -> str:
    """
    Update a semantic version string.

    Parameters:
        version (str): The version string to update.
        bump_type (str): The version increment to apply.
        pre_release (str | None): Pre-release identifier to apply or advance.

    Returns:
        str: The updated version string, or the original version if parsing or bumping fails.
    """
    prefix = "v" if version.startswith("v") else ""
    v_str = version.lstrip("v")
    try:
        ver = semver.VersionInfo.parse(v_str)

        # Rule 4: If major is 0, a breaking change should bump minor instead
        if ver.major == 0 and bump_type == "MAJOR":
            bump_type = "MINOR"

        if pre_release:
            if bump_type == "MAJOR":
                ver = ver.bump_major().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "MINOR":
                ver = ver.bump_minor().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "PATCH":
                ver = ver.bump_patch().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "PRERELEASE" or bump_type == "NONE":
                if ver.prerelease:
                    if ver.prerelease.split(".")[0] == pre_release:
                        ver = ver.bump_prerelease(token=pre_release)
                    else:
                        ver = ver.replace(prerelease=f"{pre_release}.1")
                else:
                    # SemVer Rule 9: transitioning from stable to prerelease requires bumping patch
                    ver = ver.bump_patch().replace(prerelease=f"{pre_release}.1")
        else:
            if ver.prerelease and bump_type in ("NONE", "PRERELEASE", "PATCH"):
                ver = ver.finalize_version()
            elif bump_type == "MAJOR":
                ver = ver.bump_major()
            elif bump_type == "MINOR":
                ver = ver.bump_minor()
            elif bump_type == "PATCH":
                ver = ver.bump_patch()

        return f"{prefix}{ver!s}"
    except Exception as e:
        console.print(
            f"[yellow]Failed to parse or bump version '{version}' with semver: {e}. Returning unmodified.[/yellow]"
        )
        return version


def inject_file_versions(
    files: list[str], bump_type: str, sop_data: dict, dry_run: bool, verbose: bool, pre_release: str | None = None
):
    """
    Inject bumped version strings into matching files.

    Updates the first version string found in each file when its extension matches a configured injection strategy.

    Parameters:
        files (list[str]): File paths to scan.
        bump_type (str): The SemVer bump to apply.
        sop_data (dict): SOP configuration containing the version injection matrix.
        dry_run (bool): When true, do not write changes to disk.
        verbose (bool): When true, print injection details and file-level errors.
        pre_release (str | None): Optional pre-release identifier to apply or advance.
    """
    if bump_type == "NONE" and not pre_release:
        return

    strategies = (
        sop_data.get("specifications_and_standards", {}).get("version_injection_matrix", {}).get("strategies", {})
    )
    if not strategies:
        return

    for filepath in files:
        _, ext = os.path.splitext(filepath)

        # Find matching strategy
        strategy = None
        for s in strategies.values():
            if ext in s.get("extensions", []):
                strategy = s
                break

        if not strategy:
            continue

        method = strategy.get("method")

        try:
            with open(filepath, encoding="utf-8") as f:
                file_content = f.read()

            modified = False

            def replacer(match, current_filepath=filepath):
                """
                Update a matched version string and report the change.

                Parameters:
                        match: The regex match object.
                        current_filepath: The file currently being processed.

                Returns:
                        str: The replacement text for the matched version.
                """
                nonlocal modified
                old_v = match.group(2)
                new_v = bump_version_string(old_v, bump_type, pre_release=pre_release)
                if old_v != new_v:
                    modified = True
                    if verbose or dry_run:
                        console.print(
                            f"Bumped [cyan]{current_filepath}[/cyan]: [red]{old_v}[/red] -> [green]{new_v}[/green]"
                        )
                return match.group(1) + new_v + match.group(3)

            new_content = file_content
            if method in ("root_key", "json"):
                # Matches: "version": "1.0.0"
                new_content = re.sub(r'("version"\s*:\s*")([^"]+)(")', replacer, file_content, count=1)
            elif method in ("hash_comment", "header_comment"):
                # Matches: # version: v2.0.0
                new_content = re.sub(
                    r"(#\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*)", replacer, file_content, count=1, flags=re.IGNORECASE
                )
            elif method == "slash_comment":
                # Matches: // version: v1.0.0
                new_content = re.sub(
                    r"(//\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*)", replacer, file_content, count=1, flags=re.IGNORECASE
                )
            elif method == "block_comment":
                # Matches: <!-- version: v1.0.0 -->
                new_content = re.sub(
                    r"(<!--\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*-->)",
                    replacer,
                    file_content,
                    count=1,
                    flags=re.IGNORECASE,
                )
            elif method == "python_variable":
                # Matches: __version__ = "1.0.0" or __version__ = '1.0.0'
                new_content = re.sub(
                    r'(__version__\s*=\s*[\'"])(v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)([\'"])',
                    replacer,
                    file_content,
                    count=1,
                )

            if modified and not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            if verbose:
                console.print(f"Could not inject version into {filepath}: {e}")


def group_commits_for_changelog(commits: list[str], gitmoji_matrix: list) -> dict[str, list[str]]:
    """
    Group commit subjects into changelog sections.

    Uses the `Changelog-Groups:` trailer when present to place a commit subject in one or more sections. Otherwise, falls back to the first matching gitmoji changelog group, or `Miscellaneous` when no match is found.

    Parameters:
        commits (list[str]): Raw commit strings containing a subject and optional body.
        gitmoji_matrix (list): Gitmoji metadata used to resolve legacy changelog groups.

    Returns:
        dict[str, list[str]]: Changelog groups mapped to their commit subjects.
    """
    changelog_groups = defaultdict(list)
    for commit in commits:
        parts = commit.split("---COMMIT_BODY---", 1)
        subject = parts[0]
        body = parts[1] if len(parts) > 1 else ""

        # Prefer machine-readable trailer for mixed-commit support
        trailer_match = re.search(r"^Changelog-Groups:\s*(.+)$", body, flags=re.MULTILINE)
        if trailer_match:
            # Commit can belong to multiple groups if it had secondary intents
            groups = [g.strip() for g in trailer_match.group(1).split(",")]
            for g in groups:
                if g:
                    changelog_groups[g].append(subject)
            continue

        # Legacy fallback logic
        group = "Miscellaneous"
        for entry in gitmoji_matrix:
            if entry.get("emoji") in subject or f":{entry.get('code')}:" in subject:
                group = entry.get("changelog_group", "Miscellaneous")
                break
        changelog_groups[group].append(subject)

    return changelog_groups


# ---------------------------------------------------------------------------
# Gold-standard GitHub Release notes (Issue #181)
# ---------------------------------------------------------------------------

# Preferred section order for GitHub "What's Changed" (Hybrid house style).
GITHUB_CHANGELOG_SECTION_ORDER: tuple[str, ...] = (
    "✨ Features",
    "🐛 Bug Fixes & Refactors",
    "📝 Documentation",
    "✅ Tests",
    "🔧 Chores & Internal",
    "🔒️ Security / Dependencies",
    "Miscellaneous",
)

# Map trailer / matrix changelog_group tokens → GitHub section headings.
CHANGELOG_GROUP_TO_GITHUB_SECTION: dict[str, str] = {
    "Added": "✨ Features",
    "Features": "✨ Features",
    "Fixed": "🐛 Bug Fixes & Refactors",
    "Changed": "🐛 Bug Fixes & Refactors",
    "Removed": "🐛 Bug Fixes & Refactors",
    "Deprecated": "🐛 Bug Fixes & Refactors",
    "Documentation": "📝 Documentation",
    "Docs": "📝 Documentation",
    "Tests": "✅ Tests",
    "Test": "✅ Tests",
    "Miscellaneous": "Miscellaneous",
    "Chores": "🔧 Chores & Internal",
    "Internal": "🔧 Chores & Internal",
    "Security": "🔒️ Security / Dependencies",
    "Dependencies": "🔒️ Security / Dependencies",
    "CI": "🔧 Chores & Internal",
    "Build": "🔧 Chores & Internal",
}


@dataclass(frozen=True)
class ReleaseNotesInput:
    """Inputs for gold-standard GitHub release note assembly."""

    new_tag: str
    previous_tag: str
    theme: str
    bump_type: str
    commits: list[str]
    gitmoji_matrix: list
    repo_slug: str = "Thomo1318/gitCommitGenerator"
    docs_changelog_url: str = "https://thomo1318.github.io/gitCommitGenerator/CHANGELOG.html"
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    invariant: str = (
        "the deterministic SOP / intent ranker remains semantic authority. "
        "Release automation must not invent SemVer or override Hybrid trailers."
    )
    highlights: list[str] = field(default_factory=list)
    dx_improvements: list[str] = field(default_factory=list)
    welcome_blurb: str = ""


def _normalise_tag(tag: str) -> str:
    """Normalise a release tag by trimming whitespace and ensuring it starts with ``v``.
    
    Parameters:
    	tag (str): The release tag to normalise.
    
    Returns:
    	str: The normalised tag, or an empty string when no tag is provided.
    """
    tag = (tag or "").strip()
    if not tag:
        return ""
    return tag if tag.startswith("v") else f"v{tag}"


def _version_display(tag: str) -> str:
    """
    Return a release tag without its leading `v` prefix.
    
    Parameters:
    	tag (str): The release tag to format.
    
    Returns:
    	str: The normalised tag without a leading `v`.
    """
    t = _normalise_tag(tag)
    return t[1:] if t.startswith("v") else t


def format_release_title(*, new_tag: str, theme: str) -> str:
    """
    Build the gold-standard GitHub release title.

    Parameters:
        new_tag: SemVer tag (with or without leading ``v``).
        theme: Short theme phrase after the version (no trailing period).

    Returns:
        Title like ``🚀 git-cg v0.6.0: Semantic Context integration``.
    """
    tag = _normalise_tag(new_tag)
    theme_clean = " ".join((theme or "Release").split()).strip(" :")
    return f"🚀 git-cg {tag}: {theme_clean}"


def _subject_from_commit(commit: str) -> str:
    """Extract the subject line from a formatted commit string.
    
    Parameters:
    	commit (str): A commit string containing an optional body delimiter.
    
    Returns:
    	str: The trimmed commit subject.
    """
    parts = commit.split("---COMMIT_BODY---", 1)
    return parts[0].strip()


def group_commits_for_github_sections(
    commits: list[str],
    gitmoji_matrix: list,
) -> dict[str, list[str]]:
    """
    Group commit subjects into gold-standard GitHub release sections.

    Uses the same trailer/matrix rules as ``group_commits_for_changelog``, then
    maps group tokens onto the Hybrid GitHub section headings used in v0.5/v0.6.
    """
    raw = group_commits_for_changelog(commits, gitmoji_matrix)
    out: dict[str, list[str]] = defaultdict(list)
    for group, subjects in raw.items():
        section = CHANGELOG_GROUP_TO_GITHUB_SECTION.get(group, group)
        if section not in CHANGELOG_GROUP_TO_GITHUB_SECTION.values() and section not in GITHUB_CHANGELOG_SECTION_ORDER:
            # Unknown custom group: keep name, append under Miscellaneous-like bucket
            section = group if group else "Miscellaneous"
        for subject in subjects:
            if subject not in out[section]:
                out[section].append(subject)
    return dict(out)


def format_changelog_markdown(
    *,
    new_tag: str,
    commits: list[str],
    gitmoji_matrix: list,
    use_github_sections: bool = False,
) -> str:
    """
    Format a CHANGELOG.md slice for ``new_tag``.

    Parameters:
        new_tag: Version heading (``vX.Y.Z``).
        commits: Raw commit strings from ``get_commits_since``.
        gitmoji_matrix: SOP gitmoji matrix.
        use_github_sections: When true, use gold-standard GitHub section titles.

    Returns:
        Markdown starting with ``## {tag}``.
    """
    tag = _normalise_tag(new_tag)
    if use_github_sections:
        groups = group_commits_for_github_sections(commits, gitmoji_matrix)
        order = list(GITHUB_CHANGELOG_SECTION_ORDER)
    else:
        groups = group_commits_for_changelog(commits, gitmoji_matrix)
        order = list(groups.keys())

    lines = [f"## {tag}", ""]
    # Stable order: known sections first, then any extras alphabetically.
    seen: set[str] = set()
    ordered_keys: list[str] = []
    for key in order:
        if groups.get(key):
            ordered_keys.append(key)
            seen.add(key)
    for key in sorted(k for k in groups if k not in seen and groups[k]):
        ordered_keys.append(key)

    for group in ordered_keys:
        lines.append(f"### {group}")
        lines.append("")
        for subject in groups[group]:
            lines.append(f"- {subject}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _default_boundary_rows(*, bump_type: str, theme: str) -> tuple[list[str], list[str]]:
    """
    Build default in-scope and out-of-scope release boundary rows.
    
    Parameters:
    	bump_type (str): The calculated semantic version impact.
    	theme (str): The release theme used in the in-scope description.
    
    Returns:
    	tuple[list[str], list[str]]: In-scope and out-of-scope release boundary rows.
    """
    theme_bit = theme.strip() or "this release"
    in_scope = [
        f"{theme_bit} (calculated SemVer impact: **{bump_type}**)",
        "Hybrid commit trailer-driven changelog grouping",
        "Version injection into configured project files",
        "Gold-standard GitHub release notes body (dry-run / file / optional publish)",
    ]
    out_scope = [
        "Rewriting historical GitHub releases",
        "Changing SemVer bump mathematics",
        "Epic product phases unrelated to this cut",
    ]
    return in_scope, out_scope


def _default_highlights(*, bump_type: str, theme: str, commit_count: int) -> list[str]:
    """
    Build default release highlights for the specified release.
    
    Parameters:
    	bump_type (str): The semantic version impact level for the release.
    	theme (str): The release theme used in the primary highlight.
    	commit_count (int): The number of commits included since the previous tag.
    
    Returns:
    	list[str]: Three Markdown-formatted release highlight statements.
    """
    return [
        f"**{theme.strip() or 'Release'}** — prepared as a **{bump_type}** cut from {commit_count} commit(s) since the previous tag.",
        "**Trailer-authoritative grouping** — `Changelog-Groups` / `SemVer-Impact` drive notes when present; gitmoji matrix remains the legacy fallback.",
        "**Gold-standard GitHub body** — boundary table, invariant, highlights, and compare links match the v0.5/v0.6 Releases house style.",
    ]


def build_github_release_notes(data: ReleaseNotesInput) -> str:
    """
    Assemble a structured GitHub Release markdown body.
    
    Parameters:
    	data (ReleaseNotesInput): Release metadata, scope details, highlights, and commit information.
    
    Returns:
    	str: Formatted GitHub Release notes in Markdown.
    """
    new_tag = _normalise_tag(data.new_tag)
    prev = _normalise_tag(data.previous_tag) if data.previous_tag else ""
    version = _version_display(new_tag)
    theme = " ".join((data.theme or "Release").split()).strip(" :")

    in_scope = (
        list(data.in_scope) if data.in_scope else _default_boundary_rows(bump_type=data.bump_type, theme=theme)[0]
    )
    out_scope = (
        list(data.out_of_scope)
        if data.out_of_scope
        else _default_boundary_rows(bump_type=data.bump_type, theme=theme)[1]
    )
    # Pad rows so the markdown table stays rectangular.
    while len(in_scope) < len(out_scope):
        in_scope.append("")
    while len(out_scope) < len(in_scope):
        out_scope.append("")

    highlights = (
        list(data.highlights)
        if data.highlights
        else _default_highlights(bump_type=data.bump_type, theme=theme, commit_count=len(data.commits))
    )

    welcome = (
        data.welcome_blurb.strip()
        if data.welcome_blurb
        else (f"Welcome to **`{version}`** of `git-cg`.\n\nThis release covers **{theme}**.")
    )

    sections = group_commits_for_github_sections(data.commits, data.gitmoji_matrix)

    lines: list[str] = [
        "## 📝 Release Notes",
        "",
        welcome,
        "",
        "### Boundary (read this first)",
        "",
        "| In this release | **Not** in this release |",
        "| --- | --- |",
    ]
    for left, right in zip(in_scope, out_scope, strict=True):
        lines.append(f"| {left} | {right} |")

    lines.extend(
        [
            "",
            f"**Invariant:** {data.invariant.strip()}",
            "",
            "### 🌟 Highlights",
            "",
        ]
    )
    for idx, item in enumerate(highlights, start=1):
        text = item.strip()
        if not text.startswith("**"):
            text = f"**Item {idx}.** {text}"
        lines.append(f"{idx}. {text}")
        lines.append("")

    if data.dx_improvements:
        lines.append("### 🛡️ DX & Stability Improvements")
        lines.append("")
        for idx, item in enumerate(data.dx_improvements, start=1):
            lines.append(f"{idx}. {item.strip()}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 📦 What's Changed",
            "",
            f"## {new_tag}",
            "",
        ]
    )

    ordered: list[str] = []
    seen: set[str] = set()
    for key in GITHUB_CHANGELOG_SECTION_ORDER:
        if sections.get(key):
            ordered.append(key)
            seen.add(key)
    for key in sorted(k for k in sections if k not in seen and sections[k]):
        ordered.append(key)

    for group in ordered:
        lines.append(f"### {group}")
        lines.append("")
        for subject in sections[group]:
            lines.append(f"- {subject}")
        lines.append("")

    compare = (
        f"https://github.com/{data.repo_slug}/compare/{prev}...{new_tag}"
        if prev
        else f"https://github.com/{data.repo_slug}/releases/tag/{new_tag}"
    )
    lines.extend(
        [
            f"**Full Granular Changelog**: {data.docs_changelog_url}",
            "",
            "---",
            "",
            f"**Full Changelog**: {compare}",
            "",
        ]
    )
    return "\n".join(lines)


def write_github_release_notes_file(path: str | Path, body: str) -> Path:
    """Write release notes markdown to ``path`` (parents created as needed)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return out


def create_github_release(
    *,
    tag: str,
    title: str,
    body: str,
    repo_slug: str = "Thomo1318/gitCommitGenerator",
    prerelease: bool = True,
    target: str = "main",
    dry_run: bool = False,
) -> str:
    """
    Create a GitHub Release via the ``gh`` CLI.

    Parameters:
        tag: Git tag name (``vX.Y.Z``).
        title: Release title.
        body: Markdown body.
        repo_slug: ``owner/repo``.
        prerelease: Mark as pre-release (house default for current cadence).
        target: Git ref to tag/release from.
        dry_run: When true, do not invoke ``gh``; return a summary string.

    Returns:
        URL or dry-run summary string.

    Raises:
        RuntimeError: When ``gh`` fails.
    """
    tag_n = _normalise_tag(tag)
    if dry_run:
        return (
            f"[dry-run] gh release create {tag_n} --repo {repo_slug} "
            f"--title {title!r} --target {target} "
            f"{'--prerelease ' if prerelease else ''}({len(body)} bytes notes)"
        )

    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body if body.endswith("\n") else body + "\n")
        notes_path = fh.name
    cmd = [
        "gh",
        "release",
        "create",
        tag_n,
        "--repo",
        repo_slug,
        "--title",
        title,
        "--notes-file",
        notes_path,
        "--target",
        target,
    ]
    if prerelease:
        cmd.append("--prerelease")
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8").strip()
        return out or f"https://github.com/{repo_slug}/releases/tag/{tag_n}"
    except FileNotFoundError as exc:
        raise RuntimeError("`gh` CLI not found on PATH; install GitHub CLI to publish releases.") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.output.decode("utf-8", errors="replace") if exc.output else str(exc)
        raise RuntimeError(f"gh release create failed: {detail}") from exc
    finally:
        with contextlib.suppress(Exception):
            Path(notes_path).unlink(missing_ok=True)


def resolve_release_theme(theme: str | None, *, bump_type: str, commits: list[str]) -> str:
    """
    Pick a concise theme phrase for the release title.
    
    Parameters:
        theme (str | None): Optional theme supplied for the release.
        bump_type (str): SemVer impact level used when no theme can be inferred.
        commits (list[str]): Commit messages inspected for a feature summary.
    
    Returns:
        str: The normalised theme, an inferred feature summary, or a fallback release description.
    """
    if theme and theme.strip():
        return " ".join(theme.split()).strip(" :")
    type_prefix = re.compile(r"^\S+\s+[a-z]+(?:\([^)]*\))?:\s*")
    for commit in commits:
        subject = _subject_from_commit(commit)
        if "feat" in subject.lower():
            cleaned = type_prefix.sub("", subject, count=1).strip()
            if cleaned:
                return cleaned[:72]
    return {
        "MAJOR": "Major release",
        "MINOR": "Feature release",
        "PATCH": "Patch release",
    }.get(bump_type, "Release")


def validate_release(new_tag: str) -> bool:
    """
    Check whether a release tag is available for use.
    
    Parameters:
        new_tag (str): Tag name to validate.
    
    Returns:
        bool: `True` if the tag is not found locally, `False` if it already exists locally.
    """
    try:
        subprocess.check_call(["git", "fetch", "--tags"], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        console.print(
            "[yellow]Warning: Could not fetch tags from remote (offline?). Falling back to local uniqueness check.[/yellow]"
        )

    try:
        existing_tags = (
            subprocess.check_output(["git", "tag", "-l"], stderr=subprocess.DEVNULL).decode("utf-8").splitlines()
        )
        if new_tag in existing_tags:
            console.print(
                f"[bold red]Validation Error:[/bold red] Git tag '{new_tag}' already exists locally. Release aborted to prevent collision."
            )
            return False
    except subprocess.CalledProcessError:
        pass

    return True


def _prepend_changelog_version(old_content: str, changelog_str: str, new_tag: str) -> str:
    """
    Merge a new version block into existing CHANGELOG.md content.
    
    Parameters:
        old_content (str): Existing changelog content.
        changelog_str (str): Markdown block for the new version.
        new_tag (str): Version tag to insert, with or without a leading ``v``.
    
    Returns:
        str: Changelog content with the new version block inserted, or the original content if the version is already present.
    """
    tag = new_tag if new_tag.startswith("v") else f"v{new_tag}"
    if f"## {tag}" in old_content:
        return old_content
    if old_content.startswith("# Changelog") and "## Unreleased" in old_content:
        parts = old_content.split("## Unreleased", 1)
        head = parts[0] + "## Unreleased\n\n"
        rest = parts[1]
        rest_lstripped = rest.lstrip("\n")
        if rest_lstripped.startswith("## "):
            return head + changelog_str + "\n" + rest_lstripped
        next_h2 = rest.find("\n## ")
        if next_h2 == -1:
            suffix = "" if rest.endswith("\n") else "\n"
            return head + rest.lstrip("\n") + suffix + changelog_str
        unreleased_body = rest[: next_h2 + 1]
        after = rest[next_h2 + 1 :]
        return head + unreleased_body.lstrip("\n") + changelog_str + "\n" + after
    return changelog_str + old_content


def execute_release(
    dry_run: bool,
    verbose: bool,
    pre_release: str | None = None,
    *,
    theme: str | None = None,
    notes_path: str | None = None,
    publish_github: bool = False,
    github_prerelease: bool = True,
    repo_slug: str = "Thomo1318/gitCommitGenerator",
    skip_github_notes: bool = False,
):
    """
    Prepare a release from commits since the latest Git tag.
    
    Calculates the release version, updates configured version fields, updates
    CHANGELOG.md, and prepares GitHub release notes. In dry-run mode, reports the
    planned changes without writing files or publishing a release.
    
    Parameters:
        dry_run: Simulate the release without writing files or publishing.
        verbose: Emit additional progress output.
        pre_release: Optional pre-release identifier for the generated version.
        theme: Optional theme for the GitHub release title.
        notes_path: Optional path for the generated GitHub release notes.
        publish_github: Publish the release through the GitHub CLI when true.
        github_prerelease: Mark the published GitHub release as a pre-release.
        repo_slug: GitHub repository in `owner/repository` format.
        skip_github_notes: Skip GitHub release note generation and publishing.
    """
    sop_data = get_sop_data()
    gitmoji_matrix = sop_data.get("gitmoji_reference_matrix", [])

    last_tag = get_last_tag()
    commits = get_commits_since(last_tag)

    if verbose:
        console.log(f"Found {len(commits)} commits since tag '{last_tag}'.")

    bump_type = calculate_global_bump(commits, gitmoji_matrix)

    is_prerelease = False
    try:
        if last_tag:
            is_prerelease = bool(semver.VersionInfo.parse(last_tag.lstrip("v")).prerelease)
    except Exception:
        pass

    if bump_type == "NONE" and not pre_release and not is_prerelease:
        console.print("[yellow]No changes warrant a SemVer bump. Aborting release.[/yellow]")
        return

    console.print(f"[bold green]Calculated Release Impact:[/bold green] {bump_type}")

    if not last_tag and pre_release:
        try:
            semver.VersionInfo.parse(f"0.1.0-{pre_release}.0")
        except Exception:
            console.print(
                f"[bold red]Validation Error:[/bold red] Invalid pre-release identifier '{pre_release}'. "
                "Must comply with SemVer 2.0.0."
            )
            return

    new_tag = (
        bump_version_string(last_tag, bump_type, pre_release=pre_release)
        if last_tag
        else (f"v0.1.0-{pre_release}.0" if pre_release else "v0.1.0")
    )
    if not new_tag.startswith("v"):
        new_tag = "v" + new_tag

    if new_tag == last_tag:
        console.print("[yellow]Calculated version is identical to the current tag. Aborting release.[/yellow]")
        return

    if not validate_release(new_tag):
        return

    console.print(f"[bold green]Next Version:[/bold green] {new_tag}")

    modified_files = get_modified_files_since(last_tag)
    if verbose:
        console.log(f"Scanning {len(modified_files)} modified files for version headers...")

    inject_file_versions(modified_files, bump_type, sop_data, dry_run, verbose, pre_release=pre_release)

    changelog_str = format_changelog_markdown(
        new_tag=new_tag,
        commits=commits,
        gitmoji_matrix=gitmoji_matrix,
        use_github_sections=False,
    )

    if dry_run or verbose:
        console.print(Panel(changelog_str, title=f"Generated Changelog for {new_tag}"))

    if not dry_run:
        changelog_path = "CHANGELOG.md"
        old_content = ""
        if os.path.exists(changelog_path):
            with open(changelog_path, encoding="utf-8") as f:
                old_content = f.read()
        new_content = _prepend_changelog_version(old_content, changelog_str, new_tag)
        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        console.print("[bold green]CHANGELOG.md updated.[/bold green]")

    if skip_github_notes:
        if not dry_run:
            console.print(
                f"[bold yellow]Files modified. Run `git add . && git commit -m '🔖 release: {new_tag}'` "
                f"and `git tag {new_tag}` to finish.[/bold yellow]"
            )
        return

    resolved_theme = resolve_release_theme(theme, bump_type=bump_type, commits=commits)
    title = format_release_title(new_tag=new_tag, theme=resolved_theme)
    notes_input = ReleaseNotesInput(
        new_tag=new_tag,
        previous_tag=last_tag or "",
        theme=resolved_theme,
        bump_type=bump_type,
        commits=commits,
        gitmoji_matrix=gitmoji_matrix,
        repo_slug=repo_slug,
    )
    github_body = build_github_release_notes(notes_input)

    default_notes = notes_path or f".git/GIT_CG_RELEASE_NOTES_{new_tag}.md"
    if dry_run or verbose:
        console.print(Panel(github_body, title=f"GitHub Release Notes — {title}"))

    if dry_run:
        console.print(f"[cyan]Dry-run title:[/cyan] {title}")
        console.print(f"[cyan]Notes would be written to:[/cyan] {default_notes}")
        if publish_github:
            console.print(
                create_github_release(
                    tag=new_tag,
                    title=title,
                    body=github_body,
                    repo_slug=repo_slug,
                    prerelease=github_prerelease,
                    dry_run=True,
                )
            )
        return

    written = write_github_release_notes_file(default_notes, github_body)
    console.print(f"[bold green]GitHub release notes written:[/bold green] {written}")
    console.print(f"[bold green]Release title:[/bold green] {title}")

    if publish_github:
        try:
            url = create_github_release(
                tag=new_tag,
                title=title,
                body=github_body,
                repo_slug=repo_slug,
                prerelease=github_prerelease,
                dry_run=False,
            )
            console.print(f"[bold green]GitHub release created:[/bold green] {url}")
        except RuntimeError as exc:
            console.print(f"[bold red]GitHub publish failed:[/bold red] {exc}")
            console.print(
                "[yellow]Version/changelog/notes files were still prepared. "
                "Create the tag/release manually if needed.[/yellow]"
            )
    else:
        prerelease_flag = " --prerelease" if github_prerelease else ""
        console.print(
            "[bold yellow]Files modified. Commit the version cut, tag "
            f"`{new_tag}`, then publish with "
            f"`gh release create {new_tag} --title {title!r} "
            f"--notes-file {written}{prerelease_flag}`.[/bold yellow]"
        )
