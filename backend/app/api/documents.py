import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.config import settings
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

INGEST_TIMEOUT = 300  # chunking + embedding a large PDF is slow


@router.post("/documents")
async def upload_document(file: UploadFile, user: dict = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chỉ nhận file PDF")

    contents = await file.read()
    try:
        async with httpx.AsyncClient(timeout=INGEST_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.mcp_server_url.rstrip('/')}/internal/ingest",
                files={"file": (file.filename, contents, "application/pdf")},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.exception("document ingest forwarding failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="mcp-server không phản hồi")


@router.get("/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{settings.mcp_server_url.rstrip('/')}/internal/documents")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.exception("document list forwarding failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="mcp-server không phản hồi")
