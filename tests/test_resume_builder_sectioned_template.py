from pathlib import Path

from docx import Document

from app.models.candidate import CandidateProfile
from app.services import resume_builder


def sample_profile() -> CandidateProfile:
    return CandidateProfile.model_validate({
        "personal": {
            "name": "Alex Morgan",
            "headline": "Backend Engineer",
            "email": "alex@example.com",
            "phone": "+46 70 000 0000",
            "location": "Stockholm, Sweden",
            "linkedin": "linkedin.com/in/alexmorgan",
            "github": "github.com/alexmorgan",
            "portfolio": "alexmorgan.dev",
        },
        "summary": "Software engineer focused on reliable backend services and cloud platforms.",
        "skills": ["Python", "FastAPI", "Kubernetes", "Azure", "PostgreSQL"],
        "experience": [{
            "job_title": "Backend Engineer", "company": "Example Systems", "location": "Stockholm",
            "start_date": "2022", "end_date": "Present",
            "description": ["Built and maintained production REST APIs.", "Improved service observability and deployment workflows."],
        }],
        "education": [{
            "degree": "MSc Software Engineering", "institution": "Example University",
            "location": "Sweden", "start_date": "2024", "end_date": "2026",
        }],
        "projects": [{
            "name": "Telemetry Platform", "year": "2025",
            "description": ["Built a monitoring and alerting service."], "url": "https://example.dev/project",
        }],
        "achievements": ["Improved service reliability through automated testing."],
        "certifications": ["AWS Cloud Practitioner"],
        "languages": ["English", "Swedish — learning"],
    })


def sample_tailored() -> dict:
    return {
        "summary": "Software engineer focused on reliable backend services, APIs and cloud platforms.",
        "skills": ["Python", "FastAPI", "Kubernetes", "Azure", "PostgreSQL"],
        "experience": [{
            "job_title": "Backend Engineer", "company": "Example Systems", "location": "Stockholm",
            "start_date": "2022", "end_date": "Present",
            "description": ["Built and maintained production REST APIs.", "Improved service observability and deployment workflows."],
        }],
        "keyword_gaps": [],
    }


def test_sectioned_docx_has_clear_heading_rules_and_remains_ats_safe(tmp_path: Path):
    output = tmp_path / "sectioned-cv.docx"
    profile = sample_profile()

    resume_builder._docx(profile, sample_tailored(), "sectioned", output)

    assert output.is_file()
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Alex Morgan" in text
    assert "BACKEND ENGINEER" in text
    assert "PROFESSIONAL SUMMARY" in text
    assert "TECHNICAL SKILLS" in text
    assert "Backend Development:" in text
    assert "Databases and Search:" in text
    assert "PROFESSIONAL EXPERIENCE" in text
    assert "PROJECTS" in text
    assert "EDUCATION" in text
    assert not document.tables
    # The sectioned visual separators are paragraph borders, not layout tables.
    from zipfile import ZipFile
    with ZipFile(output) as package:
        xml = package.read("word/document.xml")
    assert b"w:pBdr" in xml
    assert b"w:bottom" in xml


def test_sectioned_template_is_available_through_cv_generation(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resume_builder, "OUTPUT_DIR", tmp_path / "tailored")
    monkeypatch.setattr(resume_builder, "_grounded_tailoring", lambda _profile, _jd: sample_tailored())
    monkeypatch.setattr(resume_builder, "_ats_score", lambda *_args: {"score": 82, "checks": []})

    result = resume_builder.create_tailored_cv(
        sample_profile(),
        "A backend engineering role requiring Python, REST APIs, Kubernetes and reliable cloud services. " * 3,
        "sectioned",
        job_title="Senior Platform Engineer",
        company="Spotify",
        job_id="job:spotify:platform",
    )

    assert result["template"] == "sectioned"
    assert "Senior_Platform_Engineer" in result["filename"]
    assert "Spotify" in result["filename"]
    assert result["pdf_filename"] == Path(result["filename"]).with_suffix(".pdf").name
    assert result["review_required"] is True
    assert Path(result["download_path"]).is_file()
    assert Path(result["download_path"]).with_suffix(".json").is_file()


def test_sectioned_pdf_exports_selectable_text_and_keeps_section_headings(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resume_builder, "OUTPUT_DIR", tmp_path / "tailored")
    output_dir = tmp_path / "tailored"
    output_dir.mkdir()
    profile = sample_profile()
    source = output_dir / "alex-sectioned.docx"
    resume_builder._docx(profile, sample_tailored(), "sectioned", source)
    import json
    source.with_suffix(".json").write_text(json.dumps({
        "template": "sectioned",
        "profile": profile.model_dump(),
        "tailored_profile": sample_tailored(),
    }), encoding="utf-8")

    pdf = resume_builder.export_tailored_pdf(source.name)
    import pymupdf
    with pymupdf.open(pdf) as document:
        text = "\n".join(page.get_text("text") for page in document)
    assert "Alex Morgan" in text
    assert "PROFESSIONAL SUMMARY" in text
    assert "BACKEND ENGINEER" in text
    assert "TECHNICAL SKILLS" in text
    assert "Backend Development" in text
    assert "PROFESSIONAL EXPERIENCE" in text


def test_sectioned_skill_categories_preserve_existing_group_labels_and_never_drop_skills():
    grouped = resume_builder._sectioned_skill_groups([
        "Backend Development: C#, .NET, REST APIs",
        "Observability and Monitoring: Prometheus, Grafana",
        "UniqueSkillX",
    ])
    assert grouped == [
        ("Backend Development", "C#, .NET, REST APIs"),
        ("Observability and Monitoring", "Prometheus, Grafana"),
        ("Additional Skills", "UniqueSkillX"),
    ]

    flat = resume_builder._sectioned_skill_groups(["Python", "FastAPI", "Kubernetes", "Azure", "PostgreSQL"])
    flattened = " ".join(value for _label, value in flat)
    for skill in ("Python", "FastAPI", "Kubernetes", "Azure", "PostgreSQL"):
        assert skill in flattened


def test_sectioned_template_uses_reference_section_order_and_editable_headline(tmp_path: Path):
    profile = sample_profile()
    profile.personal.headline = "Platform Engineer"
    output = tmp_path / "ordered-sectioned-cv.docx"

    resume_builder._docx(profile, sample_tailored(), "sectioned", output)

    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    headings = [
        "PROFESSIONAL SUMMARY",
        "TECHNICAL SKILLS",
        "PROFESSIONAL EXPERIENCE",
        "PROJECTS",
        "EDUCATION",
        "ACHIEVEMENTS",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "PLATFORM ENGINEER" in text
    assert "Alex Morgan" in text
    assert not document.tables


def test_tailored_version_registry_preserves_job_context_and_exact_pdf_name(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resume_builder, "OUTPUT_DIR", tmp_path / "tailored")
    monkeypatch.setattr(resume_builder, "_grounded_tailoring", lambda _profile, _jd: sample_tailored())
    monkeypatch.setattr(resume_builder, "_ats_score", lambda *_args: {"score": 81, "checks": []})
    generated = resume_builder.create_tailored_cv(
        sample_profile(),
        ("A senior platform engineering position focused on Kubernetes, infrastructure automation, "
         "observability, reliability and cloud-native delivery. ") * 3,
        "sectioned",
        job_title="Platform Engineer",
        company="Vercel",
        job_id="job:vercel:platform",
    )
    versions = resume_builder.list_tailored_versions()
    assert versions[0]["filename"] == generated["filename"]
    assert versions[0]["pdf_filename"] == generated["pdf_filename"]
    assert versions[0]["job_title"] == "Platform Engineer"
    assert versions[0]["company"] == "Vercel"
    assert versions[0]["job_id"] == "job:vercel:platform"


def test_sectioned_template_is_accepted_by_api_contract():
    from app.main import CvTailorRequest

    request = CvTailorRequest(
        job_description=("A complete job description for a platform engineering role requiring Kubernetes, "
                         "Terraform, observability and distributed systems experience. ") * 3,
        template="sectioned",
        job_title="Senior Platform Engineer",
        company="Vercel",
    )
    assert request.template == "sectioned"
    assert request.job_title == "Senior Platform Engineer"
    assert request.company == "Vercel"
