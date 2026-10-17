import json
import re


class ParseError(Exception):
    """Model output did not follow the one-JSON-object protocol."""


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_planner_output(text: str, known_tools: set[str]) -> tuple[str, object]:
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = _JSON_RE.search(cleaned)
    if not match:
        raise ParseError("no JSON object found; reply with exactly one JSON object")
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ParseError("top-level JSON must be an object")

    if "tool" in obj:
        args = obj.get("args", {})
        if obj["tool"] not in known_tools:
            raise ParseError(f"unknown tool {obj['tool']!r}; valid tools: {sorted(known_tools)}")
        if not isinstance(args, dict):
            raise ParseError('"args" must be a JSON object')
        return "tool", {"tool": obj["tool"], "args": args}
    if "answer" in obj:
        return "answer", str(obj["answer"])
    raise ParseError('JSON must contain either "tool" or "answer"')
