import json
from pathlib import Path

from ollama import Client

from app.models.candidate import CandidateProfile


MODEL_NAME = "gemma4:e4b"

BASE_DIR = Path(__file__).resolve().parents[3]
CV_DIR = BASE_DIR / "data" / "cv"

EXTRACTED_TEXT_PATH = CV_DIR / "extracted_text.txt"
PROFILE_PATH = CV_DIR / "profile.json"


class CVAnalyzerError(Exception):
    """Raised when CV analysis fails."""


def analyze_cv() -> CandidateProfile:
    if not EXTRACTED_TEXT_PATH.exists():
        raise CVAnalyzerError(
            "No extracted CV text found. Upload a CV first."
        )

    cv_text = EXTRACTED_TEXT_PATH.read_text(
        encoding="utf-8"
    ).strip()

    if not cv_text:
        raise CVAnalyzerError(
            "The extracted CV text is empty."
        )

    schema = CandidateProfile.model_json_schema()

    prompt = f"""
You are the CV extraction component of CareerMate.

Your task is to extract structured information from the
candidate's CV.

IMPORTANT RULES:

1. Use ONLY information explicitly present in the CV.
2. Never invent experience, skills, dates, companies,
   certifications, education, languages, or achievements.
3. If information is missing, use an empty string or empty list.
4. Do not infer information that is not explicitly stated.
5. Preserve the candidate's actual meaning.
6. Return ONLY valid JSON matching the provided schema.

JSON schema:

{json.dumps(schema, indent=2)}

CV TEXT:

{cv_text}
"""

    try:
        client = Client(
            host="http://localhost:11434"
        )

        
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format=schema,
            think=False,
            options={
                "temperature": 0,
                "num_predict": 4096,
                "num_ctx": 8192,
            },
        )

        content = response.message.content or ""

        if not content.strip():
            raise CVAnalyzerError(
                "Ollama returned an empty response."
            )

        try:
            profile = CandidateProfile.model_validate_json(content)
        except Exception as exc:
            reason = getattr(response, "done_reason", None)

            if reason == "length":
                raise CVAnalyzerError(
                    "CV analysis reached the model's output limit. "
                    "Try again or reduce the amount of CV text."
                ) from exc

            raise CVAnalyzerError(
                "Ollama returned incomplete or invalid JSON. "
                "Check the model output limit and try again."
            ) from exc

        PROFILE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        PROFILE_PATH.write_text(
            profile.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return profile

    except Exception as exc:
        raise CVAnalyzerError(
            f"CV analysis failed: {exc}"
        ) from exc