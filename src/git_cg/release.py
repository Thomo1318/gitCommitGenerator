import os
import re
import subprocess
from collections import defaultdict

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
                ["git", "log", f"{tag}..HEAD", "--pretty=format:%s|%b"], stderr=subprocess.DEVNULL
            ).decode("utf-8")
        else:
            log_output = subprocess.check_output(
                ["git", "log", "--pretty=format:%s|%b"], stderr=subprocess.DEVNULL
            ).decode("utf-8")

        commits = [line for line in log_output.split("\n") if line.strip()]
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


def parse_commit_impact(subject: str, gitmoji_matrix: list) -> str:
    # Check for breaking change indicator
    if "!" in subject.split(":")[0] or "BREAKING CHANGE" in subject:
        return "MAJOR"

    # Match the cc_type
    match = re.search(r"^[^\s]+\s+([a-z]+)(\(.*?\))?:", subject)
    if match:
        cc_type = match.group(1)
        for entry in gitmoji_matrix:
            if entry.get("cc_type") == cc_type:
                return entry.get("semver_impact", "NONE")

    # Fallback checking emojis directly
    for entry in gitmoji_matrix:
        if entry.get("emoji") in subject:
            return entry.get("semver_impact", "NONE")

    return "NONE"


def calculate_global_bump(commits: list[str], gitmoji_matrix: list) -> str:
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


def bump_version_string(version: str, bump_type: str) -> str:
    # version can be v1.0.0 or 1.0.0
    prefix = "v" if version.startswith("v") else ""
    v_str = version.lstrip("v")
    try:
        major, minor, patch = map(int, v_str.split("."))
        if bump_type == "MAJOR":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "MINOR":
            minor += 1
            patch = 0
        elif bump_type == "PATCH":
            patch += 1
        return f"{prefix}{major}.{minor}.{patch}"
    except Exception:
        # If parsing fails, don't bump
        return version


def inject_file_versions(files: list[str], bump_type: str, sop_data: dict, dry_run: bool, verbose: bool):
    if bump_type == "NONE":
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

        if method == "header_comment":
            # Search top 5 lines for a version string
            try:
                with open(filepath) as f:
                    lines = f.readlines()

                modified = False
                for i in range(min(5, len(lines))):
                    # Look for something like `# version: v1.0.0` or `// version: 1.0.0`
                    match = re.search(r"(version:\s*)(v?\d+\.\d+\.\d+)", lines[i], re.IGNORECASE)
                    if match:
                        old_v = match.group(2)
                        new_v = bump_version_string(old_v, bump_type)
                        if old_v != new_v:
                            lines[i] = lines[i].replace(old_v, new_v)
                            modified = True
                            if verbose or dry_run:
                                console.print(
                                    f"Bumped [cyan]{filepath}[/cyan]: [red]{old_v}[/red] -> [green]{new_v}[/green]"
                                )
                        break

                if modified and not dry_run:
                    with open(filepath, "w") as f:
                        f.writelines(lines)
            except Exception as e:
                if verbose:
                    console.print(f"Could not inject version into {filepath}: {e}")


def execute_release(dry_run: bool, verbose: bool):
    sop_data = get_sop_data()
    gitmoji_matrix = sop_data.get("gitmoji_reference_matrix", [])

    last_tag = get_last_tag()
    commits = get_commits_since(last_tag)

    if not commits:
        console.print("[yellow]No commits found since last tag. Nothing to release.[/yellow]")
        return

    if verbose:
        console.log(f"Found {len(commits)} commits since tag '{last_tag}'.")

    bump_type = calculate_global_bump(commits, gitmoji_matrix)

    if bump_type == "NONE":
        console.print("[yellow]No changes warrant a SemVer bump. Aborting release.[/yellow]")
        return

    console.print(f"[bold green]Calculated Release Impact:[/bold green] {bump_type}")

    new_tag = bump_version_string(last_tag, bump_type) if last_tag else "v0.1.0"
    if not last_tag and not new_tag.startswith("v"):
        new_tag = "v" + new_tag

    console.print(f"[bold green]Next Version:[/bold green] {new_tag}")

    # File injection (per file)
    modified_files = get_modified_files_since(last_tag)
    if verbose:
        console.log(f"Scanning {len(modified_files)} modified files for version headers...")

    inject_file_versions(modified_files, bump_type, sop_data, dry_run, verbose)

    # Generate Changelog

    # Group commits
    changelog_groups = defaultdict(list)
    for commit in commits:
        subject = commit.split("|")[0]
        group = "Miscellaneous"
        for entry in gitmoji_matrix:
            if entry.get("emoji") in subject or f":{entry.get('code')}:" in subject:
                group = entry.get("changelog_group", "Miscellaneous")
                break
        changelog_groups[group].append(subject)

    # Format changelog
    changelog_str = f"## {new_tag}\n\n"
    for group, subjects in changelog_groups.items():
        changelog_str += f"### {group}\n"
        for sub in subjects:
            changelog_str += f"- {sub}\n"
        changelog_str += "\n"

    if dry_run or verbose:
        console.print(Panel(changelog_str, title=f"Generated Changelog for {new_tag}"))

    if not dry_run:
        # Prepend to CHANGELOG.md
        changelog_path = "CHANGELOG.md"
        old_content = ""
        if os.path.exists(changelog_path):
            with open(changelog_path) as f:
                old_content = f.read()
        with open(changelog_path, "w") as f:
            f.write(changelog_str + old_content)
        console.print("[bold green]CHANGELOG.md updated.[/bold green]")

        # We don't automatically tag here as user requested to just prepare it
        console.print(
            f"[bold yellow]Files modified. Run `git add . && git commit -m '🔖 release: {new_tag}'` and `git tag {new_tag}` to finish.[/bold yellow]"
        )
