"""Tool-calling agent loop with OpenRouter."""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from pydantic import ValidationError

from app.core.config import settings
from app.modules.agent.exceptions import (
    AgentMaxStepsExceededError,
    AgentNotConfiguredError,
    AgentToolError,
)
from app.modules.agent.schemas import ChartBlockData, SourcesBlockData
from app.modules.agent.tools.base import AgentToolRegistry
from app.modules.ai.utils.models_config import calculate_cost
from app.modules.usage.openrouter_client import create_openrouter_client
from app.modules.usage.recorder import UsageRecordContext, UsageRecorder, extract_cost_from_usage
from app.modules.usage.types import UsagePurpose

logger = logging.getLogger(__name__)


@dataclass
class AgentLoopEvent:
    """SSE event emitted during agent execution."""

    event: str
    data: dict[str, Any]


@dataclass
class AgentLoopResult:
    """Final result of an agent run."""

    message: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    blocks: list[dict[str, Any]] = field(default_factory=list)
    steps_trace: list[dict[str, Any]] = field(default_factory=list)


class AgentLoopService:
    """Own tool-calling loop against OpenRouter (OpenAI-compatible API)."""

    def __init__(
        self,
        *,
        model: str,
        system_prompt: str,
        tool_registry: AgentToolRegistry,
        api_key: str | None = None,
        max_steps: int | None = None,
        agent_key: str = "github-workspace",
        server_web_tools: bool = False,
        usage_recorder: UsageRecorder | None = None,
        usage_ctx: UsageRecordContext | None = None,
    ):
        key = api_key or settings.ai.openrouter_api_key
        if not key:
            raise AgentNotConfiguredError("OPENROUTER_API_KEY is not configured")

        self.model = model
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry
        self.agent_key = agent_key
        self.server_web_tools = server_web_tools
        self.max_steps = max_steps or settings.ai.agent_max_steps
        self.usage_recorder = usage_recorder
        self.usage_ctx = usage_ctx
        self.client = create_openrouter_client(api_key=key)

    async def run(
        self,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> AgentLoopResult:
        """Execute the loop and return the final result."""
        result: AgentLoopResult | None = None
        async for event in self.run_stream(user_message, history=history):
            if event.event == "run_complete":
                payload = event.data
                result = AgentLoopResult(
                    message=payload.get("message", ""),
                    prompt_tokens=payload.get("promptTokens", 0),
                    completion_tokens=payload.get("completionTokens", 0),
                    total_tokens=payload.get("totalTokens", 0),
                    cost_usd=payload.get("costUsd"),
                    blocks=payload.get("blocks", []),
                    steps_trace=payload.get("stepsTrace", []),
                )
        if result is None:
            raise AgentMaxStepsExceededError("Agent loop ended without a result")
        return result

    async def run_stream(
        self,
        user_message: str | list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[AgentLoopEvent]:
        """Execute the loop, yielding SSE-friendly events.

        ``user_message`` is a plain string, or OpenAI multimodal content parts
        when chat attachments (images) are present.

        ``history`` holds prior conversation turns as plain
        ``{"role": ..., "content": ...}`` messages (no tool-call replay),
        injected between the system prompt and the new user message so the
        agent can answer follow-up questions in the same session.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            *(history or []),
            {"role": "user", "content": user_message},
        ]

        prompt_tokens = 0
        completion_tokens = 0
        run_cost_usd = 0.0
        steps_trace: list[dict[str, Any]] = []
        step_index = 0

        for iteration in range(self.max_steps):
            # Refresh each turn so tool_search activations appear in schemas.
            tools = self.tool_registry.openai_tools()
            if self.server_web_tools:
                tools = [*tools, *_openrouter_web_tools()]
            create_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": cast(list[ChatCompletionMessageParam], messages),
            }
            if tools:
                create_kwargs["tools"] = cast(list[ChatCompletionToolParam], tools)
                create_kwargs["tool_choice"] = "auto"
            response = await self.client.chat.completions.create(**create_kwargs)

            usage = response.usage
            turn_prompt = 0
            turn_completion = 0
            if usage:
                turn_prompt = usage.prompt_tokens or 0
                turn_completion = usage.completion_tokens or 0
                prompt_tokens += turn_prompt
                completion_tokens += turn_completion

            if self.usage_recorder and self.usage_ctx:
                billed = await self.usage_recorder.record_chat_completion(
                    self.usage_ctx,
                    purpose=UsagePurpose.AGENT_CHAT,
                    model=self.model,
                    usage=usage,
                    response=response,
                    metadata={"iteration": iteration},
                )
                run_cost_usd += billed
            else:
                _, billed = extract_cost_from_usage(
                    usage,
                    model=self.model,
                    prompt_tokens=turn_prompt,
                    completion_tokens=turn_completion,
                )
                run_cost_usd += billed

            choice = response.choices[0]
            assistant_message = choice.message
            assistant_payload = assistant_message.model_dump(exclude_none=True)
            messages.append(assistant_payload)

            model_step = {
                "stepIndex": step_index,
                "stepType": "model",
                "name": self.model,
                "inputData": {"messages_count": len(messages)},
                "outputData": {
                    "finish_reason": choice.finish_reason,
                    "tool_calls": [tc.model_dump() for tc in (assistant_message.tool_calls or [])],
                },
            }
            steps_trace.append(model_step)
            yield AgentLoopEvent(
                event="step",
                data={
                    "type": "model",
                    "stepIndex": step_index,
                    "finishReason": choice.finish_reason,
                },
            )
            step_index += 1

            # Server-side web tools run inside OpenRouter, so the loop never sees a
            # tool_call for them. Their citations come back as message annotations —
            # replay them as one synthetic step so the trace, the audit view and the
            # sources block all still work.
            server_sources = _harvest_url_citations(assistant_payload)
            if server_sources:
                if self.usage_recorder and self.usage_ctx:
                    await self.usage_recorder.record_web_search_op(
                        self.usage_ctx,
                        count=len(server_sources),
                        metadata={"serverSide": True},
                    )
                steps_trace.append(
                    {
                        "stepIndex": step_index,
                        "stepType": "tool_result",
                        "name": "web_search",
                        "inputData": {"tool": "web_search", "serverSide": True},
                        "outputData": {
                            "serverSide": True,
                            "total": len(server_sources),
                            "sources": server_sources,
                        },
                    }
                )
                yield AgentLoopEvent(
                    event="step",
                    data={
                        "type": "tool_result",
                        "stepIndex": step_index,
                        "tool": "web_search",
                        "result": {"serverSide": True, "total": len(server_sources)},
                    },
                )
                step_index += 1

            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                content = assistant_message.content or ""
                total_tokens = prompt_tokens + completion_tokens
                cost = run_cost_usd if run_cost_usd > 0 else calculate_cost(
                    self.model, prompt_tokens, completion_tokens
                )
                blocks = _build_blocks_from_trace(steps_trace, content, agent_key=self.agent_key)
                yield AgentLoopEvent(
                    event="run_complete",
                    data={
                        "message": content,
                        "promptTokens": prompt_tokens,
                        "completionTokens": completion_tokens,
                        "totalTokens": total_tokens,
                        "costUsd": cost,
                        "blocks": blocks,
                        "stepsTrace": steps_trace,
                    },
                )
                return

            for tool_call in tool_calls:
                fn = tool_call.function
                tool_name = fn.name
                try:
                    arguments = json.loads(fn.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                yield AgentLoopEvent(
                    event="step",
                    data={
                        "type": "tool_call",
                        "stepIndex": step_index,
                        "tool": tool_name,
                        "arguments": arguments,
                    },
                )

                tool_step_input = {"tool": tool_name, "arguments": arguments}
                try:
                    tool_result = await self.tool_registry.execute(tool_name, arguments)
                    if "error" in tool_result:
                        raise AgentToolError(str(tool_result["error"]))
                except AgentToolError as exc:
                    tool_result = {"error": str(exc)}
                except Exception as exc:  # noqa: BLE001 — surface to model
                    logger.exception("Tool %s failed", tool_name)
                    tool_result = {"error": str(exc)}

                tool_step = {
                    "stepIndex": step_index,
                    "stepType": "tool_result",
                    "name": tool_name,
                    "inputData": tool_step_input,
                    "outputData": tool_result,
                }
                steps_trace.append(tool_step)
                step_index += 1

                yield AgentLoopEvent(
                    event="step",
                    data={
                        "type": "tool_result",
                        "stepIndex": step_index - 1,
                        "tool": tool_name,
                        "result": tool_result,
                    },
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    }
                )

        raise AgentMaxStepsExceededError(f"Agent exceeded maximum steps ({self.max_steps})")


def _openrouter_web_tools() -> list[dict[str, Any]]:
    """OpenRouter server tools — executed on their side, no client implementation.

    Costs are billed per web result, so `max_results` is capped by config rather
    than left to the model.
    """
    return [
        {
            "type": "openrouter:web_search",
            "parameters": {"max_results": settings.ai.web_search_max_results},
        },
        {"type": "openrouter:web_fetch"},
    ]


def _harvest_url_citations(assistant_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract `url_citation` annotations from an assistant message.

    Read from the dumped payload rather than a typed attribute: annotations are a
    provider extension and the SDK's model may not declare the field.
    """
    annotations = assistant_payload.get("annotations")
    if not isinstance(annotations, list):
        return []

    sources: list[dict[str, Any]] = []
    for annotation in annotations:
        if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
            continue
        citation = annotation.get("url_citation")
        if not isinstance(citation, dict):
            continue
        url = str(citation.get("url") or "").strip()
        if not url:
            continue
        sources.append(
            {
                "index": len(sources) + 1,
                "url": url,
                "title": citation.get("title"),
                "snippet": (str(citation.get("content"))[:600] if citation.get("content") else None),
            }
        )
    return sources


def _build_blocks_from_trace(
    steps_trace: list[dict[str, Any]],
    markdown: str,
    *,
    agent_key: str = "github-workspace",
) -> list[dict[str, Any]]:
    """Build minimal rich blocks (cards/tables) from tool results."""
    _ = markdown
    blocks: list[dict[str, Any]] = []

    if agent_key == "jira-360":
        blocks.extend(_jira_360_blocks(steps_trace))
    else:
        blocks.extend(_github_workspace_blocks(steps_trace))

    blocks.extend(_gmail_blocks(steps_trace))
    blocks.extend(_chart_blocks(steps_trace))
    blocks.extend(_sources_blocks(steps_trace))

    return blocks


_GMAIL_SNIPPET_MAX = 280
_GMAIL_CARD_MAX = 3
_GMAIL_TABLE_ROWS_MAX = 10


def _gmail_snippet(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return None
    if len(cleaned) <= _GMAIL_SNIPPET_MAX:
        return cleaned
    return cleaned[: _GMAIL_SNIPPET_MAX - 1].rstrip() + "…"


def _gmail_message_card(message: dict[str, Any]) -> dict[str, Any]:
    labels = message.get("labelIds") or []
    labels_str = ", ".join(str(label) for label in labels) if labels else None
    return {
        "type": "card",
        "title": message.get("subject") or "Email",
        "data": {
            "from": message.get("from"),
            "to": message.get("to"),
            "date": message.get("date"),
            "labels": labels_str,
            "snippet": _gmail_snippet(message.get("snippet")),
        },
    }


def _gmail_blocks(steps_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build card/table blocks from Gmail tool results (same pattern as GitHub)."""
    cards: list[dict[str, Any]] = []
    list_messages: list[dict[str, Any]] = []

    for step in steps_trace:
        if step.get("stepType") != "tool_result":
            continue
        name = step.get("name")
        output = step.get("outputData") or {}
        if "error" in output:
            continue

        if name == "gmail_get_message":
            message = output.get("message")
            if isinstance(message, dict):
                cards.append(_gmail_message_card(message))
        elif name in ("gmail_search_messages", "gmail_list_messages"):
            messages = output.get("messages")
            if isinstance(messages, list) and messages:
                list_messages = [m for m in messages if isinstance(m, dict)]

    if cards:
        return cards[:_GMAIL_CARD_MAX]

    if not list_messages:
        return []

    return [
        {
            "type": "table",
            "title": "Emails",
            "data": {
                "columns": ["from", "subject", "date"],
                "rows": [
                    {
                        "from": message.get("from"),
                        "subject": message.get("subject"),
                        "date": message.get("date"),
                    }
                    for message in list_messages[:_GMAIL_TABLE_ROWS_MAX]
                ],
            },
        }
    ]


def _normalize_source_url(url: str) -> str:
    """Key used for de-duplication: no tracking params, no trailing slash."""
    try:
        split = urlsplit(url)
    except ValueError:
        return url.strip()

    query = urlencode([(key, value) for key, value in parse_qsl(split.query, keep_blank_values=True) if not key.lower().startswith(("utm_", "fbclid", "gclid"))])
    path = split.path.rstrip("/") or "/"
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))


def _sources_blocks(steps_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect cited web sources into a single `sources` block.

    Convention-based, mirroring `_chart_blocks` (plan 013 dec. #5): any tool, on
    any agent, opts in by returning `{"sources": [{"url", "title", ...}]}`.
    Sources are de-duplicated by normalized URL, keeping first-seen order, and
    renumbered 1..n so the block matches the `[n]` markers in the answer.
    """
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for step in steps_trace:
        if step.get("stepType") != "tool_result":
            continue
        output = step.get("outputData") or {}
        if "error" in output:
            continue
        sources = output.get("sources")
        if not isinstance(sources, list):
            continue

        for source in sources:
            if not isinstance(source, dict):
                continue
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            key = _normalize_source_url(url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "index": len(items) + 1,
                    "url": url,
                    "title": source.get("title"),
                    "snippet": source.get("snippet"),
                    "publishedAt": source.get("publishedAt"),
                }
            )

    if not items:
        return []

    try:
        data = SourcesBlockData.model_validate({"items": items})
    except ValidationError:
        logger.warning("Ignoring malformed sources payload")
        return []

    return [{"type": "sources", "title": None, "data": data.model_dump()}]


def _chart_blocks(steps_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert tool results carrying a `chart` key into chart blocks.

    Convention-based (plan 008 dec. C3): any tool, on any agent, can opt in
    by returning `{"chart": {...}}` matching `ChartBlockData` — no dedicated
    `render_chart` tool needed for MVP.
    """
    blocks: list[dict[str, Any]] = []

    for step in steps_trace:
        if step.get("stepType") != "tool_result":
            continue
        output = step.get("outputData") or {}
        if "error" in output:
            continue
        chart = output.get("chart")
        if not isinstance(chart, dict):
            continue
        try:
            data = ChartBlockData.model_validate(chart)
        except ValidationError:
            logger.warning("Ignoring malformed chart payload from tool %s", step.get("name"))
            continue

        blocks.append(
            {
                "type": "chart",
                "title": chart.get("title"),
                "data": data.model_dump(),
            }
        )

    return blocks


def _jira_360_blocks(steps_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    jira_data: dict[str, Any] | None = None
    gitlab_rows: list[dict[str, Any]] = []

    for step in steps_trace:
        if step.get("stepType") != "tool_result":
            continue
        name = step.get("name")
        output = step.get("outputData") or {}
        if name == "jira_get_issue" and "error" not in output:
            jira_data = output
        if name == "gitlab_search_by_jira_key" and "error" not in output:
            for mr in output.get("merge_requests", []):
                gitlab_rows.append(
                    {
                        "type": "MR",
                        "title": mr.get("title"),
                        "state": mr.get("state"),
                        "url": mr.get("url"),
                    }
                )
            for issue in output.get("issues", []):
                gitlab_rows.append(
                    {
                        "type": "Issue",
                        "title": issue.get("title"),
                        "state": issue.get("state"),
                        "url": issue.get("url"),
                    }
                )

    if jira_data:
        blocks.append(
            {
                "type": "card",
                "title": f"Jira {jira_data.get('key', '')}",
                "data": {
                    "summary": jira_data.get("summary"),
                    "status": jira_data.get("status"),
                    "client": jira_data.get("client"),
                    "url": jira_data.get("url"),
                },
            }
        )

    if gitlab_rows:
        blocks.append(
            {
                "type": "table",
                "title": "GitLab",
                "data": {
                    "columns": ["type", "title", "state", "url"],
                    "rows": gitlab_rows,
                },
            }
        )

    return blocks


def _github_workspace_blocks(steps_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    repo_card: dict[str, Any] | None = None
    issue_rows: list[dict[str, Any]] = []

    for step in steps_trace:
        if step.get("stepType") != "tool_result":
            continue
        name = step.get("name")
        output = step.get("outputData") or {}
        if "error" in output:
            continue

        if name == "github_get_repository":
            repo_card = {
                "type": "card",
                "title": output.get("full_name", "Repository"),
                "data": {
                    "description": output.get("description"),
                    "language": output.get("language"),
                    "stars": output.get("stars"),
                    "open_issues": output.get("open_issues"),
                    "url": output.get("url"),
                },
            }
        elif name in ("github_search_issues", "github_list_repository_issues"):
            for issue in output.get("issues", []):
                issue_rows.append(
                    {
                        "number": issue.get("number"),
                        "type": issue.get("type"),
                        "title": issue.get("title"),
                        "state": issue.get("state"),
                        "url": issue.get("url"),
                    }
                )
        elif name == "github_get_issue":
            issue_rows.append(
                {
                    "number": output.get("number"),
                    "type": output.get("type"),
                    "title": output.get("title"),
                    "state": output.get("state"),
                    "url": output.get("url"),
                }
            )
        elif name == "github_search_repositories":
            repos = output.get("repositories", [])
            if repos:
                blocks.append(
                    {
                        "type": "table",
                        "title": "Repositories",
                        "data": {
                            "columns": ["full_name", "language", "stars", "url"],
                            "rows": [
                                {
                                    "full_name": repo.get("full_name"),
                                    "language": repo.get("language"),
                                    "stars": repo.get("stars"),
                                    "url": repo.get("url"),
                                }
                                for repo in repos[:10]
                            ],
                        },
                    }
                )

    if repo_card:
        blocks.insert(0, repo_card)

    if issue_rows:
        blocks.append(
            {
                "type": "table",
                "title": "Issues & PRs",
                "data": {
                    "columns": ["number", "type", "title", "state", "url"],
                    "rows": issue_rows[:15],
                },
            }
        )

    return blocks
