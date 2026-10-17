import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


async def run_migrations() -> None:
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(id text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {row["id"] for row in await conn.fetch("SELECT id FROM schema_migrations")}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                print(f"skip {path.name} (already applied)")
                continue
            sql = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations (id) VALUES ($1)", path.name)
            print(f"applied {path.name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
