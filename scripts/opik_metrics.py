import re

from opik.evaluation.metrics import BaseMetric
from opik.evaluation.metrics.score_result import ScoreResult


class FormatMetric(BaseMetric):
    def __init__(self, name: str = "CommitFormatQuality"):
        """
        Initialise a FormatMetric instance for evaluating commit message formatting.
        """
        super().__init__(name=name)
        # Matches: "<emoji> <type>[(<scope>)]: <subject>"
        self.header_regex = re.compile(
            r"^\S+\s(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|init)(\([\w\-]+\))?:\s.+$"
        )

    def score(self, output: str, **kwargs) -> ScoreResult:
        """
        Score a commit message's formatting compliance.

        Parameters:
            output (str): The commit message to evaluate.

        Returns:
            ScoreResult: Score between 0.0 and 1.0 with reasons for formatting deductions.
        """
        if not output or not isinstance(output, str) or not output.strip():
            return ScoreResult(name=self.name, value=0.0, reason="Commit message is empty or not a string.")

        lines = output.strip().split("\n")
        subject = lines[0].strip()

        reasons = []
        score = 1.0

        # Check 1: Subject length
        if len(subject) > 72:
            score -= 0.3
            reasons.append("Subject line exceeds 72 characters.")

        # Check 2: Header format (Gitmoji + type + scope + subject)
        if not self.header_regex.match(subject):
            score -= 0.5
            reasons.append("Subject line does not match convention: '<emoji> <type>[(<scope>)]: <subject>'.")

        # Check 3: Substantive commits should have specific headers
        # We look for SemVer-Impact or Change-Types if it has any body content.
        # This is a soft check.
        if len(lines) > 1:
            has_semver = any(line.startswith("SemVer-Impact:") for line in lines)
            has_changes = any(line.startswith("Change-Types:") for line in lines)
            if not has_semver or not has_changes:
                score -= 0.2
                reasons.append("Missing required trailers (SemVer-Impact and Change-Types must both be present).")

        # Clamp score between 0.0 and 1.0
        final_score = max(0.0, min(1.0, score))

        reason_str = " | ".join(reasons) if reasons else "Perfect formatting."
        return ScoreResult(name=self.name, value=final_score, reason=reason_str)
