import pytest

from app.agent.parser import ParseError, parse_planner_output

KNOWN = {"rag_search", "calendar_read"}


def test_parses_clean_tool_call():
    kind, val = parse_planner_output('{"tool": "rag_search", "args": {"query": "x"}}', KNOWN)
    assert kind == "tool" and val == {"tool": "rag_search", "args": {"query": "x"}}


def test_parses_clean_answer():
    kind, val = parse_planner_output('{"answer": "hello"}', KNOWN)
    assert kind == "answer" and val == "hello"


def test_parses_fenced_json():
    kind, _ = parse_planner_output('```json\n{"answer": "hi"}\n```', KNOWN)
    assert kind == "answer"


def test_parses_json_wrapped_in_prose():
    kind, val = parse_planner_output('Sure! {"tool": "calendar_read", "args": {}} there', KNOWN)
    assert kind == "tool" and val["tool"] == "calendar_read"


def test_missing_args_defaults_to_empty_dict():
    kind, val = parse_planner_output('{"tool": "calendar_read"}', KNOWN)
    assert kind == "tool" and val["args"] == {}


def test_unknown_tool_raises():
    with pytest.raises(ParseError):
        parse_planner_output('{"tool": "nope", "args": {}}', KNOWN)


def test_non_json_raises():
    with pytest.raises(ParseError):
        parse_planner_output("I think the answer is 42.", KNOWN)


def test_non_dict_args_raises():
    with pytest.raises(ParseError):
        parse_planner_output('{"tool": "rag_search", "args": "x"}', KNOWN)
