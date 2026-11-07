
"""Evidence-grounded CV tailoring, ATS checks and DOCX export."""
from __future__ import annotations
import json, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from app.models.candidate import CandidateProfile
from app.services.ai_provider import AIProviderError, generate_text

BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE_DIR / "data" / "cv" / "tailored"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STOP = {"about","above","after","again","against","along","also","among","and","any","are","around","because","been","before","being","between","both","but","can","could","does","each","from","have","into","its","more","most","must","need","only","our","over","role","should","such","than","that","the","their","them","then","there","these","they","this","those","through","under","upon","using","very","was","were","what","when","where","which","while","will","with","within","work","you","your","years","experience","candidate","strong","including","looking","team"}

def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,}", text.lower()) if x not in STOP and len(x)>2}

def _profile_text(p: dict) -> str:
    return json.dumps(p, ensure_ascii=False)

def _grounded_tailoring(profile: CandidateProfile, jd: str) -> dict:
    """Use AI for editing/reordering, while constraining source facts to the saved profile."""
    source = profile.model_dump()
    schema = {
      "summary": "string",
      "skills": ["existing skill strings only, reordered by relevance"],
      "experience": [{"job_title":"existing","company":"existing","location":"existing","start_date":"existing","end_date":"existing","description":["rephrased evidence-based bullet"]}],
      "keyword_gaps": ["JD terms not evidenced by the source CV"]
    }
    prompt = f"""You are a careful professional CV editor. Tailor this candidate profile to the job description.
Return ONLY valid JSON with keys summary, skills, experience, keyword_gaps.
STRICT FACT RULES: do not invent or imply tools, skills, employers, job titles, dates, metrics, qualifications, responsibilities or achievements. Preserve every factual claim. You may shorten, clarify, reorder and rephrase existing evidence. Skills must be selected verbatim from the candidate's skills list. Experience entries must retain the same employer/title/dates and may only rewrite the existing description bullets. Do not add unsupported JD keywords; put them in keyword_gaps.
Candidate profile JSON: {json.dumps(source, ensure_ascii=False)}
Job description: {json.dumps(jd, ensure_ascii=False)}
Expected shape: {json.dumps(schema)}
"""
    json_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "experience": {"type": "array", "items": {"type": "object", "properties": {
                "job_title": {"type": "string"}, "company": {"type": "string"}, "location": {"type": "string"},
                "start_date": {"type": "string"}, "end_date": {"type": "string"},
                "description": {"type": "array", "items": {"type": "string"}}
            }, "required": ["job_title","company","location","start_date","end_date","description"]}},
            "keyword_gaps": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["summary","skills","experience","keyword_gaps"]
    }
    raw = generate_text(prompt, json_schema=json_schema, max_tokens=3500, temperature=0.1, context_window=8192)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("AI returned invalid tailoring data. Try again with another model.") from exc
    # Guard identity and employment chronology: AI cannot change these source fields.
    original = source["experience"]
    tailored = result.get("experience", [])
    if len(tailored) != len(original):
        raise ValueError("AI changed the number of employment records. No CV was exported.")
    for old, new in zip(original, tailored):
        for key in ("job_title","company","location","start_date","end_date"):
            if str(new.get(key,"")).strip() != str(old.get(key,"")).strip():
                raise ValueError("AI changed an employment fact. No CV was exported.")
    allowed_skills = set(source["skills"])
    result["skills"] = [s for s in result.get("skills", []) if s in allowed_skills]
    # Conservative evidence gate: reject bullets that introduce unsupported numbers
    # or have too little lexical overlap with the source employment evidence.
    for index, old_exp in enumerate(original):
        source_bullets = old_exp.get("description", [])
        source_text = " ".join(source_bullets)
        source_tokens = _tokens(source_text)
        safe_bullets = []
        for bullet in tailored[index].get("description", []):
            bullet = str(bullet).strip()
            bullet_tokens = _tokens(bullet)
            numbers = set(re.findall(r"\d+(?:[.,]\d+)?%?", bullet))
            source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?%?", source_text))
            overlap = len(bullet_tokens & source_tokens) / max(1, len(bullet_tokens))
            if numbers.issubset(source_numbers) and overlap >= 0.30:
                safe_bullets.append(bullet)
        tailored[index]["description"] = safe_bullets or source_bullets
    # If the rewritten summary is not anchored in the original profile, keep the source summary.
    summary_tokens = _tokens(str(result.get("summary", "")))
    profile_tokens = _tokens(_profile_text(source))
    if summary_tokens and len(summary_tokens & profile_tokens) / max(1, len(summary_tokens)) < 0.25:
        result["summary"] = source.get("summary", "")
    return result

TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "c#", ".net", "asp.net", "rest api", "rest apis",
    "sql", "postgresql", "postgres", "mysql", "oracle", "pl/sql", "mongodb", "opensearch",
    "rabbitmq", "kafka", "amqp", "mqtt", "signalr", "microservices", "distributed systems",
    "docker", "kubernetes", "helm", "terraform", "aws", "azure", "gcp", "gitops", "argocd",
    "teamcity", "jenkins", "github actions", "artifactory", "ci/cd", "prometheus", "grafana",
    "opentelemetry", "jaeger", "splunk", "fluent bit", "fluentd", "linux", "bash", "powershell",
    "pytest", "xunit", "nunit", "tdd", "oauth", "oidc", "iam", "rbac", "tls", "http", "https",
    "blazor", "razor", "asp.net core", "entity framework", "ef core", "node.js", "react", "fastapi",
    "python scripting", "automation", "observability", "monitoring", "incident management", "sre",
    "site reliability", "platform engineering", "backend development", "api design", "unit testing",
    "integration testing", "message queues", "queue routing", "authentication", "authorization"
}

SKILL_ALIASES = {"k8s": "kubernetes", "postgres": "postgresql", "dotnet": ".net", "aspnet": "asp.net"}

def _normalise_skill(value: str) -> str:
    item = re.sub(r"\s+", " ", value.lower().strip())
    return SKILL_ALIASES.get(item, item)

def _ats_score(profile: CandidateProfile, jd: str, tailored: dict) -> dict:
    """Estimate coverage of identifiable technical/role requirements, not every JD word."""
    jd_lower = jd.lower()
    detected = sorted(skill for skill in TECH_SKILLS if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", jd_lower))
    cv_parts = [tailored.get("summary", ""), *tailored.get("skills", [])]
    for exp in tailored.get("experience", []):
        cv_parts.extend(exp.get("description", []))
    for project in profile.projects:
        cv_parts.extend([project.name, *project.description])
    cv_parts.extend(profile.achievements)
    cv_text = " ".join(cv_parts).lower()
    matched = [skill for skill in detected if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", cv_text)]
    missing = [skill for skill in detected if skill not in matched]
    keyword_score = round(100 * len(matched) / max(1, len(detected))) if detected else 0
    fields = [
        ("Name", bool(profile.personal.name)),
        ("Contact details", bool(profile.personal.email or profile.personal.phone)),
        ("Professional summary", bool(tailored.get("summary"))),
        ("Skills", bool(tailored.get("skills"))),
        ("Work experience", bool(tailored.get("experience"))),
        ("Education", bool(profile.education)),
    ]
    checks = [{"name": label, "passed": passed} for label, passed in fields]
    completeness = round(100 * sum(passed for _, passed in fields) / len(fields))
    # Keep this explicitly an estimate: skill coverage is weighted more heavily than section presence.
    score = round(keyword_score * 0.8 + completeness * 0.2) if detected else completeness
    return {
        "score": score,
        "keyword_match_score": keyword_score,
        "section_completeness_score": completeness,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "detected_requirement_count": len(detected),
        "checks": checks,
        "threshold": 70,
        "status": "ready_for_review" if score >= 70 else "needs_improvement",
        "disclaimer": "Indicative coverage of identifiable technical and role requirements only. This is not an ATS vendor score or a prediction of interview success. Review the job requirements and every CV statement before applying."
    }

def _add_paragraph_bottom_border(paragraph, color: str = "D9E1F2", size: str = "8", space: str = "5") -> None:
    """Add a real Word paragraph rule without introducing a layout table."""
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), space)
    bottom.set(qn("w:color"), color)
    borders.append(bottom)


_SECTIONED_SKILL_CATEGORIES: list[tuple[str, set[str]]] = [
    ("Backend Development", {"c#", ".net", "dotnet", "asp.net", "asp.net core mvc", "python", "typescript", "rest api", "rest apis", "blazor", "tdd", "nunit", "xunit", "signalr", "microservices", "node.js", "go", "fastapi"}),
    ("Databases and Search", {"oracle", "oracle database", "pl/sql", "postgresql", "postgres", "mongodb", "opensearch", "complex sql queries", "sql", "mysql"}),
    ("Messaging and Distributed Systems", {"rabbitmq", "amqp", "mqtt", "queue routing", "kafka", "message queues", "distributed systems"}),
    ("CI/CD and GitOps", {"teamcity", "jfrog artifactory", "artifactory", "nuget", "argo cd", "argocd", "git", "gitops", "github actions", "jenkins", "ci/cd"}),
    ("Cloud and Infrastructure", {"aws", "azure", "microsoft azure", "terraform", "acr", "azure container registry", "kubernetes", "docker", "helm", "gcp"}),
    ("Observability and Monitoring", {"opentelemetry", "prometheus", "grafana", "jaeger", "splunk", "fluent bit", "fluentbit", "fluentd", "fluent-bit"}),
    ("Security", {"iam", "rbac", "role based access control", "authentication", "authorisation", "authorization", "oauth", "oidc", "tls"}),
    ("AI and LLM Engineering", {"generative ai", "large language models", "llms", "llm application prototyping", "prompt engineering"}),
    ("AI-Assisted Development", {"github copilot", "claude code", "cursor", "ai-assisted code review", "test generation", "responsible ai", "data privacy", "gdpr"}),
]


def _sectioned_skill_groups(skills: list[str]) -> list[tuple[str, str]]:
    """Keep source skill text intact while presenting it in CV-style categories."""
    clean = [str(skill).strip() for skill in skills if str(skill).strip()]
    if not clean:
        return []

    # If the saved profile already contains category: skills lines, preserve the
    # user's chosen labels and wording rather than reclassifying them.
    explicitly_grouped: list[tuple[str, str]] = []
    ungrouped: list[str] = []
    for item in clean:
        if ":" in item and len(item.split(":", 1)[0]) <= 48:
            label, body = item.split(":", 1)
            if body.strip():
                explicitly_grouped.append((label.strip(), body.strip()))
        else:
            ungrouped.append(item)
    if explicitly_grouped:
        if ungrouped:
            explicitly_grouped.append(("Additional Skills", " · ".join(ungrouped)))
        return explicitly_grouped

    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.casefold().strip()).replace("–", "-")

    buckets: dict[str, list[str]] = {label: [] for label, _ in _SECTIONED_SKILL_CATEGORIES}
    additional: list[str] = []
    for skill in clean:
        key = normalize(skill)
        match = next((label for label, aliases in _SECTIONED_SKILL_CATEGORIES if key in {normalize(x) for x in aliases}), None)
        if match:
            buckets[match].append(skill)
        else:
            additional.append(skill)
    groups = [(label, " · ".join(values)) for label, values in buckets.items() if values]
    if additional:
        groups.append(("Additional Skills", " · ".join(additional)))
    return groups


def _docx(profile: CandidateProfile, tailored: dict, template: str, output: Path):
    # The data workspace may be reset or its generated folders removed after
    # this module is imported. Recreate the destination immediately before save.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    sec = doc.sections[0]
    if template == "sectioned":
        sec.top_margin = Inches(.62); sec.bottom_margin = Inches(.62)
        sec.left_margin = Inches(.68); sec.right_margin = Inches(.68)
    else:
        sec.top_margin = Inches(.55); sec.bottom_margin = Inches(.55)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(9.2 if template == "sectioned" else 9)
    styles["Normal"].paragraph_format.space_after = Pt(4 if template == "sectioned" else 3)
    styles["Normal"].paragraph_format.line_spacing = 1.08 if template == "sectioned" else 1.0

    headline = (profile.personal.headline or "").strip()
    if not headline and profile.experience:
        headline = profile.experience[0].job_title.strip()
    if template == "sectioned":
        name = doc.add_paragraph()
        name.alignment = 1
        name.paragraph_format.space_after = Pt(1)
        run = name.add_run(profile.personal.name or "Candidate")
        run.bold = True; run.font.size = Pt(22); run.font.color.rgb = RGBColor(25, 39, 68)

        if headline:
            role = doc.add_paragraph()
            role.alignment = 1
            role.paragraph_format.space_after = Pt(4)
            role_run = role.add_run(headline.upper())
            role_run.bold = True; role_run.font.size = Pt(10.5); role_run.font.color.rgb = RGBColor(79, 70, 190)

        contact_primary = "  |  ".join(x for x in [profile.personal.location, profile.personal.phone, profile.personal.email] if x)
        contact_links = "  |  ".join(x for x in [
            f"LinkedIn: {profile.personal.linkedin}" if profile.personal.linkedin else "",
            f"GitHub: {profile.personal.github}" if profile.personal.github else "",
            f"Portfolio: {profile.personal.portfolio}" if profile.personal.portfolio else "",
        ] if x)
        for contact_text in (contact_primary, contact_links):
            if contact_text:
                contact = doc.add_paragraph()
                contact.alignment = 1
                contact.paragraph_format.space_after = Pt(2)
                contact.paragraph_format.keep_with_next = True
                contact_run = contact.add_run(contact_text)
                contact_run.font.size = Pt(8.2); contact_run.font.color.rgb = RGBColor(91, 105, 130)
        if doc.paragraphs:
            _add_paragraph_bottom_border(doc.paragraphs[-1], "8C83F6", "14", "7")
    else:
        title = doc.add_paragraph()
        title.alignment = 1 if template == "modern" else 0
        title.paragraph_format.space_after = Pt(3 if template == "sectioned" else 1)
        r = title.add_run(profile.personal.name or "Candidate")
        r.bold = True
        r.font.size = Pt(21 if template != "compact" else 18)
        r.font.color.rgb = RGBColor(7, 20, 46)

        contact_items = [profile.personal.email, profile.personal.phone, profile.personal.location,
                         profile.personal.linkedin, profile.personal.github, profile.personal.portfolio]
        contact = "  •  ".join(x for x in contact_items if x)
        p = doc.add_paragraph(contact)
        p.alignment = 1 if template == "modern" else 0
        p.paragraph_format.space_after = Pt(3)
        for run in p.runs:
            run.font.size = Pt(8); run.font.color.rgb = RGBColor(91, 105, 130)

    def heading(label):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(11 if template == "sectioned" else 7)
        p.paragraph_format.space_after = Pt(4 if template == "sectioned" else 3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(label.upper())
        run.bold = True
        run.font.size = Pt(10.2 if template == "sectioned" else 10)
        if template == "sectioned":
            run.font.color.rgb = RGBColor(34, 48, 73)
            _add_paragraph_bottom_border(p, "D9DDF0", "7", "4")
        else:
            run.font.color.rgb = RGBColor(8, 105, 190) if template == "modern" else RGBColor(7, 20, 46)
        return p

    def add_right_date(paragraph, date_text: str):
        if not date_text:
            return
        paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(6.92), WD_TAB_ALIGNMENT.RIGHT)
        date_run = paragraph.add_run("\t" + date_text)
        date_run.font.size = Pt(8.2)
        date_run.font.color.rgb = RGBColor(101, 113, 136)

    if tailored.get("summary"):
        heading("Professional Summary")
        para = doc.add_paragraph(tailored["summary"])
        if template == "sectioned": para.paragraph_format.space_after = Pt(5)
    if tailored.get("skills"):
        heading("Technical Skills" if template == "sectioned" else "Core Skills")
        if template == "sectioned":
            for category, values in _sectioned_skill_groups(tailored["skills"]):
                skill_line = doc.add_paragraph()
                skill_line.paragraph_format.space_after = Pt(2.5)
                label_run = skill_line.add_run(category + ": ")
                label_run.bold = True; label_run.font.color.rgb = RGBColor(39, 53, 77)
                value_run = skill_line.add_run(values)
                value_run.font.color.rgb = RGBColor(46, 55, 72)
        else:
            doc.add_paragraph(" • ".join(tailored["skills"]))
    if tailored.get("experience"):
        heading("Professional Experience")
        for exp in tailored["experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(5 if template == "sectioned" else 1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.keep_with_next = True
            r = p.add_run(f'{exp.get("job_title", "")}  |  {exp.get("company", "")}')
            r.bold = True
            if template == "sectioned":
                r.font.size = Pt(9.8); r.font.color.rgb = RGBColor(36, 51, 78)
            dates = " - ".join(x for x in [exp.get("start_date", ""), exp.get("end_date", "")] if x)
            add_right_date(p, dates if template == "sectioned" else "")
            if template == "sectioned" and exp.get("location"):
                loc = doc.add_paragraph(exp.get("location", ""))
                loc.paragraph_format.space_after = Pt(2)
                loc.paragraph_format.keep_with_next = True
                for run in loc.runs:
                    run.font.size = Pt(8.2); run.font.color.rgb = RGBColor(101, 113, 136)
            elif dates:
                dr = p.add_run(f"   {dates}")
                dr.font.size = Pt(8.5); dr.font.color.rgb = RGBColor(101, 113, 136)
            for bullet in exp.get("description", []):
                bp = doc.add_paragraph(bullet, style="List Bullet")
                bp.paragraph_format.left_indent = Inches(.22)
                bp.paragraph_format.first_line_indent = Inches(-.14)
                bp.paragraph_format.space_after = Pt(2.2 if template == "sectioned" else 2.5)
    if profile.projects:
        heading("Projects")
        for project in profile.projects:
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(3 if template == "sectioned" else 1)
            p.add_run(project.name).bold = True
            if template == "sectioned": add_right_date(p, project.year)
            elif project.year:
                year = p.add_run(f"   {project.year}")
                year.font.color.rgb = RGBColor(101, 113, 136); year.font.size = Pt(8.5)
            for bullet in project.description:
                bp = doc.add_paragraph(bullet, style="List Bullet")
                bp.paragraph_format.left_indent = Inches(.22)
                bp.paragraph_format.first_line_indent = Inches(-.14)
                bp.paragraph_format.space_after = Pt(2 if template == "sectioned" else 3)
            if project.url:
                link = doc.add_paragraph(project.url)
                link.paragraph_format.space_after = Pt(3)
                for run in link.runs:
                    run.font.color.rgb = RGBColor(79, 99, 181); run.font.size = Pt(8)
    if profile.education:
        heading("Education")
        for item in profile.education:
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            p.add_run(f"{item.degree}  |  {item.institution}").bold = True
            if template == "sectioned": add_right_date(p, " - ".join(x for x in [item.start_date, item.end_date] if x))
            if item.location:
                loc = doc.add_paragraph(item.location)
                loc.paragraph_format.space_after = Pt(2)
                for run in loc.runs:
                    run.font.size = Pt(8.2); run.font.color.rgb = RGBColor(101, 113, 136)
            if template != "sectioned" and (item.start_date or item.end_date):
                dates = p.add_run(f"   {item.start_date} - {item.end_date}")
                dates.font.size = Pt(8.5); dates.font.color.rgb = RGBColor(101, 113, 136)
    if profile.achievements:
        heading("Achievements")
        for achievement in profile.achievements:
            bp = doc.add_paragraph(achievement, style="List Bullet")
            bp.paragraph_format.left_indent = Inches(.22)
            bp.paragraph_format.first_line_indent = Inches(-.14)
            bp.paragraph_format.space_after = Pt(2)
    for label, values in [("Certifications", profile.certifications), ("Languages", profile.languages)]:
        if values:
            heading(label)
            doc.add_paragraph("  ·  ".join(values) if template == "sectioned" else " • ".join(values))

    doc.save(output)
    # Verify that the generated DOCX remains text-based and single-column/table-free.
    check = Document(output)
    extracted = "\n".join(paragraph.text for paragraph in check.paragraphs)
    if not extracted.strip() or (profile.personal.name and profile.personal.name not in extracted):
        raise ValueError("Generated DOCX failed its text extraction check.")
    if check.tables:
        raise ValueError("Generated DOCX contains tables; ATS-safe layout validation failed.")

def _filename_part(value: str, fallback: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_")
    return (slug[:54].rstrip("_") or fallback)


def create_tailored_cv(
    profile: CandidateProfile,
    jd: str,
    template: str,
    *,
    job_title: str = "",
    company: str = "",
    job_id: str = "",
) -> dict:
    if template not in {"classic", "modern", "compact", "sectioned"}:
        raise ValueError("Choose one of the available templates: classic, modern, compact, sectioned.")
    if len(jd.strip()) < 100:
        raise ValueError("Please provide the full job description (at least 100 characters).")
    tailored = _grounded_tailoring(profile, jd)
    ats = _ats_score(profile, jd, tailored)
    candidate_part = _filename_part(profile.personal.name or "Candidate", "Candidate")
    role_part = _filename_part(job_title or "Target_Role", "Target_Role")
    company_part = _filename_part(company or "Employer", "Employer")
    version_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    # Filename is meaningful in Downloads, the document library and ATS uploads.
    # It intentionally preserves role and employer, rather than a generic current.pdf.
    filename = f"{candidate_part}_{role_part}_{company_part}_{version_stamp}_{template}.docx"
    path = OUTPUT_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    _docx(profile, tailored, template, path)
    created_at = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "template": template,
        "created_at": created_at,
        "job_title": str(job_title or "").strip(),
        "company": str(company or "").strip(),
        "job_id": str(job_id or "").strip(),
        "profile": profile.model_dump(),
        "tailored_profile": tailored,
        "ats": ats,
    }
    path.with_suffix(".json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "filename": filename,
        "pdf_filename": path.with_suffix(".pdf").name,
        "download_path": str(path),
        "template": template,
        "job_title": str(job_title or "").strip(),
        "company": str(company or "").strip(),
        "tailored_profile": tailored,
        "ats": ats,
        "review_required": True,
        "message": "CV generated. Review every statement before using it.",
    }


def export_tailored_pdf(filename: str) -> Path:
    """Render the reviewed DOCX's saved structured snapshot to a selectable-text PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable
    safe = Path(filename).name
    if safe != filename or not safe.endswith(".docx"):
        raise ValueError("Invalid CV filename.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = OUTPUT_DIR / safe
    snapshot_path = source.with_suffix(".json")
    if not source.is_file() or not snapshot_path.is_file():
        raise FileNotFoundError("Tailored CV snapshot not found.")
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    profile = data["profile"]; tailored = data["tailored_profile"]
    output = source.with_suffix(".pdf")
    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=14*mm, bottomMargin=14*mm)
    styles = getSampleStyleSheet()
    is_sectioned = data.get("template") == "sectioned"
    styles.add(ParagraphStyle(name="CVName", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22 if is_sectioned else 19, leading=25 if is_sectioned else 22, alignment=1 if is_sectioned else 0, textColor=colors.HexColor("#192744" if is_sectioned else "#07142e"), spaceAfter=2))
    styles.add(ParagraphStyle(name="CVHeadline", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, alignment=1, textColor=colors.HexColor("#5146BE"), spaceAfter=4))
    styles.add(ParagraphStyle(name="CVContact", parent=styles["Normal"], fontName="Helvetica", fontSize=8.1, leading=10.5, alignment=1, textColor=colors.HexColor("#5B6982"), spaceAfter=2))
    styles.add(ParagraphStyle(name="CVSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10 if is_sectioned else 9, leading=13 if is_sectioned else 12, textColor=colors.HexColor("#223049" if is_sectioned else "#0878c9"), spaceBefore=10 if is_sectioned else 9, spaceAfter=4))
    styles.add(ParagraphStyle(name="CVBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.7 if is_sectioned else 8.5, leading=11.5 if is_sectioned else 11, textColor=colors.HexColor("#39465f" if is_sectioned else "#333333"), spaceAfter=3.5))
    styles.add(ParagraphStyle(name="CVMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=7.9, leading=9.5, textColor=colors.HexColor("#657188"), spaceAfter=2))
    styles.add(ParagraphStyle(name="CVSkill", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.4, leading=11, textColor=colors.HexColor("#2E3748"), spaceAfter=2.5))
    esc=lambda x: str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n", " ")
    contact=profile.get("personal",{})
    if is_sectioned:
        story=[Paragraph(esc(contact.get("name") or "Candidate"),styles["CVName"])]
        experience = tailored.get("experience") or profile.get("experience") or []
        headline = contact.get("headline") or (experience[0].get("job_title") if experience else "")
        if headline:
            story.append(Paragraph(esc(headline.upper()), styles["CVHeadline"]))
        primary=" | ".join(str(contact.get(k,"")) for k in ("location","phone","email") if contact.get(k))
        links=" | ".join(f"{label}: {contact.get(key)}" for label,key in (("LinkedIn","linkedin"),("GitHub","github"),("Portfolio","portfolio")) if contact.get(key))
        if primary: story.append(Paragraph(esc(primary), styles["CVContact"]))
        if links: story.append(Paragraph(esc(links), styles["CVContact"]))
        story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#8C83F6"), spaceBefore=5, spaceAfter=3))
    else:
        story=[Paragraph(esc(contact.get("name") or "Candidate"),styles["CVName"])]
        line=" | ".join(str(contact.get(k,"")) for k in ("email","phone","location","linkedin","github","portfolio") if contact.get(k))
        if line: story.append(Paragraph(esc(line),styles["CVBody"]))

    def section(title):
        story.extend([Spacer(1, 2), Paragraph(esc(title.upper()), styles["CVSection"])])
        if is_sectioned:
            story.append(HRFlowable(width="100%", thickness=0.65, color=colors.HexColor("#D9DDF0"), spaceBefore=0, spaceAfter=4))
    if tailored.get("summary"):
        section("Professional Summary")
        story.append(Paragraph(esc(tailored["summary"]),styles["CVBody"]))
    if tailored.get("skills"):
        section("Technical Skills" if is_sectioned else "Core Skills")
        if is_sectioned:
            for category, values in _sectioned_skill_groups(tailored["skills"]):
                story.append(Paragraph(f"<b>{esc(category)}:</b> {esc(values)}", styles["CVSkill"]))
        else:
            story.append(Paragraph(esc(" • ".join(tailored["skills"])),styles["CVBody"]))
    if tailored.get("experience"):
        section("Professional Experience")
        for e in tailored["experience"]:
            dates=" - ".join(x for x in [e.get("start_date", ""), e.get("end_date", "")] if x)
            date_html=f"<font color='#657188' size='8'>  {esc(dates)}</font>" if dates and is_sectioned else ""
            story.append(Paragraph(f"<b>{esc(e.get('job_title',''))} | {esc(e.get('company',''))}</b>{date_html}",styles["CVBody"]))
            if is_sectioned and e.get("location"):
                story.append(Paragraph(esc(e.get("location")), styles["CVMeta"]))
            for b in e.get("description",[]): story.append(Paragraph("• "+esc(b),styles["CVBody"]))
    if profile.get("projects"):
        section("Projects")
        for project in profile.get("projects", []):
            year = f"  <font color='#657188' size='8'>{esc(project.get('year',''))}</font>" if project.get("year") else ""
            story.append(Paragraph(f"<b>{esc(project.get('name',''))}</b>{year}", styles["CVBody"]))
            for bullet in project.get("description", []): story.append(Paragraph("• " + esc(bullet), styles["CVBody"]))
            if project.get("url"): story.append(Paragraph(esc(project["url"]), styles["CVMeta"]))
    if profile.get("education"):
        section("Education")
        for e in profile["education"]:
            dates=" - ".join(x for x in [e.get("start_date", ""), e.get("end_date", "")] if x)
            date_html=f"  <font color='#657188' size='8'>{esc(dates)}</font>" if dates else ""
            story.append(Paragraph(f"<b>{esc(e.get('degree',''))} | {esc(e.get('institution',''))}</b>{date_html}",styles["CVBody"]))
            if is_sectioned and e.get("location"):
                story.append(Paragraph(esc(e.get("location")), styles["CVMeta"]))
    if profile.get("achievements"):
        section("Achievements")
        for achievement in profile["achievements"]: story.append(Paragraph("• " + esc(achievement),styles["CVBody"]))
    for label,key in (("Certifications","certifications"),("Languages","languages")):
        if profile.get(key):
            section(label)
            story.append(Paragraph(esc(" • ".join(profile[key])),styles["CVBody"]))
    doc.build(story)
    # Verify selectable text and expected identity are present in the exported PDF.
    import pymupdf
    with pymupdf.open(output) as rendered:
        extracted = "\\n".join(page.get_text("text") for page in rendered)
        if not extracted.strip() or (profile.get("personal", {}).get("name") and profile["personal"]["name"] not in extracted):
            raise ValueError("Generated PDF failed its text extraction check.")
        if len(rendered) > 4:
            raise ValueError("Generated PDF exceeds the four-page CV layout check.")
    return output


def list_tailored_versions(limit: int = 50) -> list[dict]:
    versions=[]
    for snapshot_path in OUTPUT_DIR.glob("*.json"):
        try:
            data=json.loads(snapshot_path.read_text(encoding="utf-8"))
            docx_name=snapshot_path.with_suffix(".docx").name
            if not (OUTPUT_DIR/docx_name).is_file(): continue
            versions.append({
                "filename": docx_name,
                "pdf_filename": snapshot_path.with_suffix(".pdf").name,
                "template": data.get("template", "classic"),
                "created_at": data.get("created_at", ""),
                "ats_score": data.get("ats", {}).get("score"),
                "job_title": data.get("job_title", ""),
                "company": data.get("company", ""),
                "job_id": data.get("job_id", ""),
            })
        except (OSError,ValueError,TypeError):
            continue
    versions.sort(key=lambda item:item.get("created_at",""),reverse=True)
    return versions[:max(1,min(limit,200))]
