"""Tests for rich-block construction from agent run traces."""

from app.core.config import settings
from app.modules.agent.services.agent_loop import (
    _build_blocks_from_trace,
    _chart_blocks,
    _gmail_blocks,
    _harvest_url_citations,
    _openrouter_web_tools,
    _sources_blocks,
)


def _tool_result_step(name: str, output: dict) -> dict:
    return {"stepType": "tool_result", "name": name, "outputData": output}


def test_chart_blocks_builds_line_chart_from_convention():
    steps = [
        _tool_result_step(
            "some_tool",
            {
                "chart": {
                    "chartType": "line",
                    "title": "Revenue",
                    "xLabel": "Month",
                    "yLabel": "USD",
                    "series": [
                        {
                            "name": "2026",
                            "points": [{"x": "Jan", "y": 100}, {"x": "Feb", "y": 120}],
                        }
                    ],
                }
            },
        )
    ]

    blocks = _chart_blocks(steps)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "chart"
    assert blocks[0]["title"] == "Revenue"
    assert blocks[0]["data"]["chartType"] == "line"
    assert blocks[0]["data"]["series"][0]["name"] == "2026"
    assert blocks[0]["data"]["series"][0]["points"][0] == {"x": "Jan", "y": 100}


def test_chart_blocks_ignores_malformed_payload():
    steps = [
        _tool_result_step("some_tool", {"chart": {"chartType": "line"}}),  # missing series
        _tool_result_step("other_tool", {"chart": "not-a-dict"}),
        _tool_result_step("failing_tool", {"error": "boom", "chart": {"chartType": "bar", "series": []}}),
    ]

    blocks = _chart_blocks(steps)

    assert blocks == []


def test_chart_blocks_ignores_tools_without_chart_key():
    steps = [_tool_result_step("github_get_repository", {"full_name": "acme/repo"})]

    assert _chart_blocks(steps) == []


def test_build_blocks_from_trace_appends_chart_after_agent_specific_blocks():
    steps = [
        _tool_result_step(
            "github_get_repository",
            {"full_name": "acme/repo", "description": "desc"},
        ),
        _tool_result_step(
            "some_tool",
            {
                "chart": {
                    "chartType": "bar",
                    "series": [{"name": "s", "points": [{"x": 1, "y": 2}]}],
                }
            },
        ),
    ]

    blocks = _build_blocks_from_trace(steps, "markdown", agent_key="github-workspace")

    assert [b["type"] for b in blocks] == ["card", "chart"]


def test_gmail_blocks_get_message_builds_card():
    steps = [
        _tool_result_step(
            "gmail_get_message",
            {
                "message": {
                    "from": "a@example.com",
                    "to": "b@example.com",
                    "subject": "Hello",
                    "date": "2026-07-25T07:22:00+02:00",
                    "labelIds": ["INBOX", "CATEGORY_PERSONAL"],
                    "snippet": "Hi there, we are hiring.",
                }
            },
        )
    ]

    blocks = _gmail_blocks(steps)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "card"
    assert blocks[0]["title"] == "Hello"
    assert blocks[0]["data"]["from"] == "a@example.com"
    assert blocks[0]["data"]["to"] == "b@example.com"
    assert blocks[0]["data"]["labels"] == "INBOX, CATEGORY_PERSONAL"
    assert blocks[0]["data"]["snippet"] == "Hi there, we are hiring."


def test_gmail_blocks_search_only_builds_table():
    steps = [
        _tool_result_step(
            "gmail_search_messages",
            {
                "messages": [
                    {
                        "from": "a@example.com",
                        "subject": "One",
                        "date": "2026-07-25",
                    },
                    {
                        "from": "c@example.com",
                        "subject": "Two",
                        "date": "2026-07-24",
                    },
                ]
            },
        )
    ]

    blocks = _gmail_blocks(steps)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "table"
    assert blocks[0]["title"] == "Emails"
    assert blocks[0]["data"]["columns"] == ["from", "subject", "date"]
    assert len(blocks[0]["data"]["rows"]) == 2
    assert blocks[0]["data"]["rows"][0]["subject"] == "One"


def test_gmail_blocks_search_plus_get_returns_only_cards():
    steps = [
        _tool_result_step(
            "gmail_search_messages",
            {
                "messages": [
                    {"from": "a@example.com", "subject": "One", "date": "2026-07-25"},
                ]
            },
        ),
        _tool_result_step(
            "gmail_get_message",
            {
                "message": {
                    "from": "a@example.com",
                    "to": "me@example.com",
                    "subject": "One",
                    "date": "2026-07-25",
                    "snippet": "Body preview",
                }
            },
        ),
    ]

    blocks = _gmail_blocks(steps)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "card"
    assert blocks[0]["title"] == "One"


def test_gmail_blocks_ignores_error_steps():
    steps = [
        _tool_result_step("gmail_get_message", {"error": "boom", "message": {"subject": "Nope"}}),
        _tool_result_step("gmail_search_messages", {"error": "nope", "messages": [{"subject": "X"}]}),
    ]

    assert _gmail_blocks(steps) == []


def test_gmail_blocks_truncates_long_snippet():
    long_snippet = "x" * 400
    steps = [
        _tool_result_step(
            "gmail_get_message",
            {"message": {"subject": "Long", "snippet": long_snippet}},
        )
    ]

    blocks = _gmail_blocks(steps)

    assert blocks[0]["data"]["snippet"] is not None
    assert len(blocks[0]["data"]["snippet"]) <= 280
    assert blocks[0]["data"]["snippet"].endswith("…")


def test_build_blocks_from_trace_includes_gmail_cards():
    steps = [
        _tool_result_step(
            "gmail_get_message",
            {"message": {"subject": "Offer", "from": "hr@example.com", "snippet": "Hi"}},
        )
    ]

    blocks = _build_blocks_from_trace(steps, "found it", agent_key="github-workspace")

    assert [block["type"] for block in blocks] == ["card"]
    assert blocks[0]["title"] == "Offer"


def test_sources_block_dedupes_and_renumbers():
    """Any tool opting into the `sources` convention contributes (plan 013 dec. #5)."""
    steps = [
        _tool_result_step(
            "web_search",
            {
                "sources": [
                    {"index": 1, "url": "https://a.example/post/?utm_source=news", "title": "A"},
                    {"index": 2, "url": "https://b.example", "title": "B"},
                ]
            },
        ),
        # A later web_fetch of the same page, differing only by tracking params
        # and a trailing slash, must not become a second entry.
        _tool_result_step(
            "web_fetch",
            {"sources": [{"index": 1, "url": "https://a.example/post", "title": "A again"}]},
        ),
    ]

    blocks = _sources_blocks(steps)

    assert len(blocks) == 1
    items = blocks[0]["data"]["items"]
    assert [item["index"] for item in items] == [1, 2]
    assert [item["title"] for item in items] == ["A", "B"]


def test_sources_block_skips_failed_steps_and_entries_without_a_url():
    steps = [
        _tool_result_step("web_search", {"error": "boom", "sources": [{"url": "https://nope.example"}]}),
        _tool_result_step("web_search", {"sources": [{"title": "no url"}, "not-a-dict", {"url": "  "}]}),
    ]

    assert _sources_blocks(steps) == []


def test_sources_block_absent_when_no_tool_opts_in():
    assert _sources_blocks([_tool_result_step("memory_search", {"memories": []})]) == []


def test_build_blocks_from_trace_includes_sources():
    steps = [_tool_result_step("web_search", {"sources": [{"url": "https://a.example", "title": "A"}]})]

    blocks = _build_blocks_from_trace(steps, "answer [1]", agent_key="general")

    assert [block["type"] for block in blocks] == ["sources"]


def test_harvest_url_citations_reads_server_side_annotations():
    """Server-mode searches surface only as message annotations."""
    payload = {
        "annotations": [
            {"type": "url_citation", "url_citation": {"url": "https://a.example", "title": "A", "content": "snippet"}},
            {"type": "something_else", "url_citation": {"url": "https://ignored.example"}},
            {"type": "url_citation", "url_citation": {"title": "no url"}},
        ]
    }

    sources = _harvest_url_citations(payload)

    assert sources == [{"index": 1, "url": "https://a.example", "title": "A", "snippet": "snippet"}]


def test_harvest_url_citations_tolerates_a_message_without_annotations():
    assert _harvest_url_citations({"content": "plain answer"}) == []


def test_openrouter_web_tools_caps_result_count_from_config():
    tools = _openrouter_web_tools()

    assert [tool["type"] for tool in tools] == ["openrouter:web_search", "openrouter:web_fetch"]
    assert tools[0]["parameters"]["max_results"] == settings.ai.web_search_max_results
