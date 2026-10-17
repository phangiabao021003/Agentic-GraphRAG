"""Manual e2e for the agent loop: uv run python scripts/e2e_agent.py "your question" """
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import run_agent  # noqa: E402


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Vitamin C có tác dụng gì?"
    async for event in run_agent([], query):
        print(event, "\n")


asyncio.run(main())
