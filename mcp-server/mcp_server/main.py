import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile

from app.utils import check_qdrant
from app.ingest import get_all_doc_ids, ingest_pdf
from app.tools.registry import mcp
from app.models import qdrant_client

mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # FastAPI does not run a mounted sub-app's lifespan; without this the MCP
    # session manager never starts and every MCP request dies with
    # "Session terminated".
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    qdrant_ok = check_qdrant(qdrant_client)
    return {
        "status": "ok" if qdrant_ok else "degraded",
        "qdrant": qdrant_ok,
        "models_loaded": True,
    }


@app.post("/internal/ingest")
async def internal_ingest(file: UploadFile):
    tmp_path = Path(tempfile.gettempdir()) / file.filename
    contents = await file.read()
    tmp_path.write_bytes(contents)
    try:
        result = ingest_pdf(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    return result


@app.get("/internal/documents")
def internal_documents():
    return {"doc_ids": get_all_doc_ids()}


# Mounted last so the explicit routes above win. The sub-app serves the MCP
# endpoint at its own internal "/mcp" path — mounting it at "/mcp" would
# double the path to /mcp/mcp (a 404 that hid until the first real MCP client
# connected in sub-project #5).
app.mount("/", mcp_app)
