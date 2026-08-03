"""POST /import/xlsx — upload workbook, import to star schema, report + job status."""
import csv
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..importer import Importer
from ..cache import set_job, get_job, invalidate_aggregates

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/gsheet")
def import_gsheet(db: Session = Depends(get_db)):
    """Live-sync the configured Google Sheet's Sales-Funnel tab into the star schema.
    Authoritative refresh: drops the prior sheet-sourced SALE rows, then re-imports."""
    from ..gsheet import fetch_rows
    rows = fetch_rows()
    if len(rows) < 3:
        raise HTTPException(400, "sheet returned too few rows (unexpected layout)")
    job_id = uuid.uuid4().hex[:12]
    tmp = Path(tempfile.gettempdir()) / f"gsheet_{job_id}.csv"
    with tmp.open("w", encoding="utf-8", newline="") as out:
        csv.writer(out).writerows(rows)
    logger.info("gsheet import {} started ({} rows)", job_id, len(rows))
    try:
        db.execute(text("DELETE FROM fact_transaction WHERE source_row LIKE 'Sales!R%'"))  # replace, not merge
        result = Importer(db).run_csv(str(tmp))
        result.update(status="done", job_id=job_id, source="google-sheet")
        set_job(job_id, result)
        invalidate_aggregates()
        logger.success("gsheet import {} done: {}", job_id, result["inserted"])
        return result
    except Exception as e:
        db.rollback()
        logger.exception("gsheet import {} failed", job_id)
        raise HTTPException(500, f"google sheet import failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)


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


@router.post("/funnel-csv")
def import_funnel_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a Sales-Funnel CSV (e.g. exported from the Google Sheet) and load it.
    Authoritative refresh: drops prior sheet-sourced SALE rows, then re-imports."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "expected a .csv (Sales Funnel export)")
    job_id = uuid.uuid4().hex[:12]
    tmp = Path(tempfile.gettempdir()) / f"funnel_{job_id}.csv"
    with tmp.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    logger.info("funnel-csv import {} started ({})", job_id, file.filename)
    try:
        db.execute(text("DELETE FROM fact_transaction WHERE source_row LIKE 'Sales!R%'"))
        result = Importer(db).run_csv(str(tmp))
        result.update(status="done", job_id=job_id, source="funnel-csv")
        set_job(job_id, result)
        invalidate_aggregates()
        logger.success("funnel-csv import {} done: {}", job_id, result["inserted"])
        return result
    except Exception as e:
        db.rollback()
        logger.exception("funnel-csv import {} failed", job_id)
        raise HTTPException(500, f"funnel import failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/status/{job_id}")
def import_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return job
