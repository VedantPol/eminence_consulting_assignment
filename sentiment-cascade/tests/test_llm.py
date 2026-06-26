"""Tool-output parsing + few-shot construction — no network."""
from types import SimpleNamespace

import pytest

from app.llm import TOOL_NAME, ClaudeBackend, _ToolOutput


def _fake_response(tool_input):
    block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input=tool_input)
    text = SimpleNamespace(type="text", text="ignored")
    return SimpleNamespace(content=[text, block])


def test_parse_extracts_tool_use_block():
    resp = _fake_response({
        "overall_sentiment": "mixed", "confidence": 0.88,
        "aspects": [{"target": "fees", "polarity": "negative", "excerpt": "high fees"}],
        "rationale": "app good, fees bad", "language": "en"})
    out = ClaudeBackend._parse(resp)
    assert isinstance(out, _ToolOutput)
    assert out.overall_sentiment.value == "mixed"
    assert out.aspects[0].target == "fees"


def test_parse_raises_without_tool_block():
    resp = SimpleNamespace(content=[SimpleNamespace(type="text", text="no tool here")])
    with pytest.raises(ValueError):
        ClaudeBackend._parse(resp)


def test_parse_rejects_malformed_enum():
    from pydantic import ValidationError

    resp = _fake_response({"overall_sentiment": "furious", "confidence": 1.0,
                           "aspects": [], "language": "en"})
    with pytest.raises(ValidationError):
        ClaudeBackend._parse(resp)


def test_fewshot_messages_are_well_formed():
    msgs = ClaudeBackend._build_fewshot_messages()
    # triples of user / assistant(tool_use) / user(tool_result)
    assert len(msgs) % 3 == 0
    assert msgs[1]["content"][0]["type"] == "tool_use"
    assert msgs[2]["content"][0]["type"] == "tool_result"
    # tool_use id matches the following tool_result id
    assert msgs[1]["content"][0]["id"] == msgs[2]["content"][0]["tool_use_id"]
