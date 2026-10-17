import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile

from mcp_server.utils import check_qdrant
from mcp_server.ingest import get_all_doc_ids, ingest_pdf
from mcp_server.tools.registry import mcp
from mcp_server.models import qdrant_client

mcp = mcp.streamable_http_mcp()


@asynccontextmanager
async def lifespan(mcp: FastAPI):
    # FastAPI does not run a mounted sub-mcp's lifespan; without this the MCP
    # session manager never starts and every MCP request dies with
    # "Session terminated".
    async with mcp.session_manager.run():
        yield


mcp = FastAPI(lifespan=lifespan)


@mcp.get("/health")
def health():
    qdrant_ok = check_qdrant(qdrant_client)
    return {
        "status": "ok" if qdrant_ok else "degraded",
        "qdrant": qdrant_ok,
        "models_loaded": True,
    }


@mcp.post("/internal/ingest")
async def internal_ingest(file: UploadFile):
    tmp_path = Path(tempfile.gettempdir()) / file.filename
    contents = await file.read()
    tmp_path.write_bytes(contents)
    try:
        result = ingest_pdf(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    return result


@mcp.get("/internal/documents")
def internal_documents():
    return {"doc_ids": get_all_doc_ids()}


# Mounted last so the explicit routes above win. The sub-mcp serves the MCP
# endpoint at its own internal "/mcp" path — mounting it at "/mcp" would
# double the path to /mcp/mcp (a 404 that hid until the first real MCP client
# connected in sub-project #5).
mcp.mount("/", mcp)
