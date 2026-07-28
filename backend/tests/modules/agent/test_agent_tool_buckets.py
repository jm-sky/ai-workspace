"""Tool-bucket allow-list validation for the agent editor.

The bucket list lives in three places (build_tool_registry, this router, and
AgentsSettingsPage.vue). When they drift, saving a built-in agent through the
editor 422s — which is exactly what happened when the `wiki` bucket shipped.
"""

import pytest
from fastapi import HTTPException

from app.modules.agent.registry import BUILTIN_AGENTS
from app.modules.agent.routers.agents import TOOL_BUCKETS, _validate_tool_profile


def test_every_builtin_agent_profile_is_accepted():
    """Regression: `wiki` was missing, so github-workspace could not be saved."""
    for agent in BUILTIN_AGENTS.values():
        _validate_tool_profile(list(agent.tool_profile))


@pytest.mark.parametrize("bucket", ["wiki", "web"])
def test_newer_buckets_are_allowed(bucket):
    _validate_tool_profile([bucket])


def test_unknown_bucket_is_rejected_with_422():
    with pytest.raises(HTTPException) as exc_info:
        _validate_tool_profile(["memory", "telepathy"])

    assert exc_info.value.status_code == 422
    assert "telepathy" in exc_info.value.detail


def test_bucket_list_covers_every_profile_entry_in_the_registry():
    used = {bucket for agent in BUILTIN_AGENTS.values() for bucket in agent.tool_profile}

    assert used <= set(TOOL_BUCKETS)
