"""Tests for rich-block construction from agent run traces."""

from app.modules.agent.services.agent_loop import (
    _build_blocks_from_trace,
    _chart_blocks,
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
