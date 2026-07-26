"""POST /import/xlsx — upload workbook, import to star schema, report + job status."""
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from ..db import get_db
from ..importer import Importer
from ..cache import set_job, get_job, invalidate_aggregates

router = APIRouter(prefix="/import", tags=["import"])


# sync def: polars read + inserts block for seconds — run in the threadpool,
# not the event loop, so concurrent requests aren't stalled during an import.
@router.post("/xlsx")
def import_xlsx(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "expected an .xlsx workbook")
    job_id = uuid.uuid4().hex[:12]
    set_job(job_id, {"status": "running", "file": file.filename})
    tmp = Path(tempfile.gettempdir()) / f"upload_{job_id}.xlsx"
    with tmp.open("wb") as out:                    # stream to disk, don't hold whole file in RAM
        shutil.copyfileobj(file.file, out)
    logger.info("import job {} started ({})", job_id, file.filename)
    try:
        result = Importer(db).run(str(tmp))
        result["status"] = "done"
        result["job_id"] = job_id
        set_job(job_id, result)
        invalidate_aggregates()
        logger.success("import job {} done: {}", job_id, result["inserted"])
        return result
    except Exception as e:
        db.rollback()
        logger.exception("import job {} failed", job_id)
        set_job(job_id, {"status": "error", "error": str(e)})
        raise HTTPException(500, f"import failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/status/{job_id}")
def import_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return job
