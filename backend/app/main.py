from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile

from app.services.cv_parser import CVParserError, extract_cv_text


app = FastAPI(
    title="CareerMate",
    description="Local AI-powered job search and application assistant",
    version="0.1.0",
)


BASE_DIR = Path(__file__).resolve().parents[2]

CV_DIR = BASE_DIR / "data" / "cv"
CV_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "CareerMate",
    }


@app.post("/api/cv/upload")
async def upload_cv(file: UploadFile) -> dict[str, object]:

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Supported formats: PDF, DOCX, TXT.",
        )

    destination = CV_DIR / f"current{extension}"

    try:
        contents = await file.read()

        destination.write_bytes(contents)

        text = extract_cv_text(destination)

        if not text:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No text could be extracted from the CV. "
                    "The PDF may be scanned/image-only."
                ),
            )

        text_path = CV_DIR / "extracted_text.txt"
        text_path.write_text(
            text,
            encoding="utf-8",
        )

        return {
            "success": True,
            "filename": file.filename,
            "format": extension,
            "characters": len(text),
            "text": text,
        }

    except CVParserError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc