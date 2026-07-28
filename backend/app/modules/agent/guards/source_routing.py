"""Source routing guard.

Small models (e.g. Gemini Flash) sometimes answer from the wrong system in a
360° fan-out. After a turn we cheaply check: did the user *explicitly* name a
source, and did the agent actually query it? Mismatches become a warning
appended to the answer and a trace step — never a hard failure.
"""

from dataclasses import dataclass

# provider -> distinctive keyword fragments (lowercased substring match), PL + EN.
# Kept deliberately narrow to avoid false positives (e.g. "email" usually means
# "the client's email address", not "search Gmail").
SOURCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "jira": ("jira",),
    "gitlab": ("gitlab", "git lab"),
    "github": ("github", "git hub"),
    "gmail": ("gmail",),
    "teams": ("teams",),
    "web": ("w internecie", "w sieci", "web search", "search the web", "google it"),
}


def provider_of_tool(tool_name: str) -> str | None:
    """Map a tool name like ``jira_get_issue`` to its provider (``jira``)."""
    for provider in SOURCE_KEYWORDS:
        if tool_name == provider or tool_name.startswith(f"{provider}_"):
            return provider
    return None


@dataclass(frozen=True)
class SourceRoutingWarning:
    """A source the user asked for but the agent did not query."""

    provider: str
    reason: str  # "not_used" | "unavailable"
    message: str


def check_source_mismatch(
    *,
    user_message: str,
    tools_used: list[str],
    available_providers: set[str],
) -> list[SourceRoutingWarning]:
    """Return warnings for explicitly-named sources the agent skipped."""
    text = user_message.lower()
    used = {p for tool in tools_used if (p := provider_of_tool(tool))}

    warnings: list[SourceRoutingWarning] = []
    for provider, keywords in SOURCE_KEYWORDS.items():
        if not any(keyword in text for keyword in keywords):
            continue
        if provider in used:
            continue
        if provider in available_providers:
            warnings.append(
                SourceRoutingWarning(
                    provider=provider,
                    reason="not_used",
                    message=(f"You asked about {provider}, but the agent answered " f"without querying it. The {provider} data may be missing."),
                )
            )
        else:
            warnings.append(
                SourceRoutingWarning(
                    provider=provider,
                    reason="unavailable",
                    message=(f"You asked about {provider}, but that integration is not " f"available for this agent yet."),
                )
            )
    return warnings


def format_warnings(warnings: list[SourceRoutingWarning]) -> str:
    """Render warnings as a Markdown note appended to the agent answer."""
    if not warnings:
        return ""
    lines = ["> ⚠️ **Source check**"]
    lines.extend(f"> - {w.message}" for w in warnings)
    return "\n".join(lines)
