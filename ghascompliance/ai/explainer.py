"""AI Output Explainer — turns raw compliance violations into a readable report."""

from ghascompliance.ai.prompts import EXPLAINER_SYSTEM_PROMPT
from ghascompliance.ai.providers.factory import get_provider


def explain_results(
    repository: str,
    violations: list[str],
    total_errors: int,
    provider_name: str | None = None,
    model: str | None = None,
) -> str:
    """
    Generate a human-readable explanation of compliance violations.

    Args:
        repository:    GitHub repository (owner/repo).
        violations:    List of raw violation log messages captured during the run.
        total_errors:  Total violation count reported by the tool.
        provider_name: AI provider to use (defaults to AI_PROVIDER env var or groq).
        model:         Optional model override.

    Returns:
        AI-generated report as a plain string.
    """
    provider = get_provider(provider_name, model)

    if not violations:
        user_message = (
            f"Repository: {repository}\n"
            f"Total unacceptable alerts: {total_errors}\n\n"
            "No individual violation details were captured. "
            "The errors may be API failures rather than security violations. "
            "Please provide a brief summary of what this likely means."
        )
    else:
        violation_block = "\n".join(f"- {v}" for v in violations)
        user_message = (
            f"Repository: {repository}\n"
            f"Total unacceptable alerts: {total_errors}\n\n"
            f"Violations:\n{violation_block}"
        )

    return provider.chat(
        [{"role": "user", "content": user_message}],
        EXPLAINER_SYSTEM_PROMPT,
    )
