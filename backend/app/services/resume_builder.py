
"""Evidence-grounded CV tailoring, ATS checks and DOCX export."""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
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

def _docx(profile: CandidateProfile, tailored: dict, template: str, output: Path):
    # The data workspace may be reset or its generated folders removed after
    # this module is imported. Recreate the destination immediately before save.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(.55); sec.bottom_margin = Inches(.55)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"; styles["Normal"].font.size = Pt(9)
    styles["Normal"].paragraph_format.space_after = Pt(3)
    title = doc.add_paragraph()
    title.alignment = 1 if template == "modern" else 0
    r = title.add_run(profile.personal.name or "Candidate")
    r.bold=True; r.font.size=Pt(21 if template!="compact" else 18)
    r.font.color.rgb = RGBColor(7, 20, 46)
    contact = " | ".join(x for x in [profile.personal.email, profile.personal.phone, profile.personal.location, profile.personal.linkedin, profile.personal.github, profile.personal.portfolio] if x)
    p=doc.add_paragraph(contact); p.alignment = 1 if template == "modern" else 0
    def heading(label):
        p=doc.add_paragraph()
        run=p.add_run(label.upper()); run.bold=True; run.font.size=Pt(10)
        run.font.color.rgb=RGBColor(8, 105, 190) if template=="modern" else RGBColor(7,20,46)
        return p
    if tailored.get("summary"):
        heading("Professional Summary"); doc.add_paragraph(tailored["summary"])
    if tailored.get("skills"):
        heading("Core Skills")
        doc.add_paragraph(" • ".join(tailored["skills"]))
    if tailored.get("experience"):
        heading("Professional Experience")
        for exp in tailored["experience"]:
            p=doc.add_paragraph()
            r=p.add_run(f'{exp.get("job_title","")} | {exp.get("company","")}'); r.bold=True
            dates=" – ".join(x for x in [exp.get("start_date",""),exp.get("end_date","")] if x)
            if dates: p.add_run("  "+dates)
            for bullet in exp.get("description",[]):
                doc.add_paragraph(bullet, style="List Bullet")
    if profile.projects:
        heading("Projects")
        for project in profile.projects:
            p = doc.add_paragraph()
            p.add_run(project.name).bold = True
            if project.year:
                p.add_run(f"  {project.year}")
            for bullet in project.description:
                doc.add_paragraph(bullet, style="List Bullet")
            if project.url:
                doc.add_paragraph(project.url)
    if profile.achievements:
        heading("Achievements")
        for achievement in profile.achievements:
            doc.add_paragraph(achievement, style="List Bullet")
    if profile.education:
        heading("Education")
        for item in profile.education:
            p=doc.add_paragraph()
            p.add_run(f"{item.degree} | {item.institution}").bold=True
            if item.start_date or item.end_date: p.add_run(f"  {item.start_date} – {item.end_date}")
    for label, values in [("Certifications",profile.certifications),("Languages",profile.languages)]:
        if values:
            heading(label); doc.add_paragraph(" • ".join(values))
    doc.save(output)
    # Verify that the generated DOCX remains text-based and single-column/table-free.
    check = Document(output)
    extracted = "\\n".join(paragraph.text for paragraph in check.paragraphs)
    if not extracted.strip() or (profile.personal.name and profile.personal.name not in extracted):
        raise ValueError("Generated DOCX failed its text extraction check.")
    if check.tables:
        raise ValueError("Generated DOCX contains tables; ATS-safe layout validation failed.")

def create_tailored_cv(profile: CandidateProfile, jd: str, template: str) -> dict:
    if template not in {"classic","modern","compact"}:
        raise ValueError("Choose one of the available templates: classic, modern, compact.")
    if len(jd.strip()) < 100:
        raise ValueError("Please provide the full job description (at least 100 characters).")
    tailored = _grounded_tailoring(profile, jd)
    ats = _ats_score(profile, jd, tailored)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+","-", profile.personal.name or "candidate").strip("-").lower()
    version_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    filename = f"{safe_name}-{template}-{version_stamp}.docx"
    path = OUTPUT_DIR / filename
    # Do not rely only on the module-import mkdir: local workspace reset or
    # manual cleanup can remove this directory while the API is running.
    path.parent.mkdir(parents=True, exist_ok=True)
    _docx(profile, tailored, template, path)
    snapshot = {"template": template, "created_at": datetime.now(timezone.utc).isoformat(), "profile": profile.model_dump(), "tailored_profile": tailored, "ats": ats}
    path.with_suffix(".json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"filename":filename,"download_path":str(path),"template":template,"tailored_profile":tailored,"ats":ats,
            "review_required":True,"message":"CV generated. Review every statement before using it."}


def export_tailored_pdf(filename: str) -> Path:
    """Render the reviewed DOCX's saved structured snapshot to a selectable-text PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
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
    styles.add(ParagraphStyle(name="CVName", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=22, textColor=colors.HexColor("#07142e"), spaceAfter=4))
    styles.add(ParagraphStyle(name="CVSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#0878c9"), spaceBefore=9, spaceAfter=4))
    styles.add(ParagraphStyle(name="CVBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, spaceAfter=3))
    esc=lambda x: str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n", " ")
    story=[Paragraph(esc(profile.get("personal",{}).get("name") or "Candidate"),styles["CVName"])]
    contact=profile.get("personal",{})
    line=" | ".join(str(contact.get(k,"")) for k in ("email","phone","location","linkedin","github","portfolio") if contact.get(k))
    if line: story.append(Paragraph(esc(line),styles["CVBody"]))
    def section(title): story.extend([Spacer(1,2),Paragraph(esc(title.upper()),styles["CVSection"])])
    if tailored.get("summary"): section("Professional Summary"); story.append(Paragraph(esc(tailored["summary"]),styles["CVBody"]))
    if tailored.get("skills"): section("Core Skills"); story.append(Paragraph(esc(" • ".join(tailored["skills"])),styles["CVBody"]))
    if tailored.get("experience"):
        section("Professional Experience")
        for e in tailored["experience"]:
            story.append(Paragraph(f"<b>{esc(e.get('job_title',''))} | {esc(e.get('company',''))}</b>",styles["CVBody"]))
            for b in e.get("description",[]): story.append(Paragraph("• "+esc(b),styles["CVBody"]))
    if profile.get("projects"):
        section("Projects")
        for project in profile.get("projects", []):
            story.append(Paragraph(f"<b>{esc(project.get('name',''))}</b> {esc(project.get('year',''))}", styles["CVBody"]))
            for bullet in project.get("description", []): story.append(Paragraph("• " + esc(bullet), styles["CVBody"]))
            if project.get("url"): story.append(Paragraph(esc(project["url"]), styles["CVBody"]))
    if profile.get("achievements"):
        section("Achievements")
        for achievement in profile.get("achievements", []): story.append(Paragraph("• " + esc(achievement), styles["CVBody"]))
    if profile.get("education"):
        section("Education")
        for e in profile["education"]: story.append(Paragraph(f"<b>{esc(e.get('degree',''))} | {esc(e.get('institution',''))}</b>",styles["CVBody"]))
    for label,key in (("Certifications","certifications"),("Languages","languages")):
        if profile.get(key): section(label); story.append(Paragraph(esc(" • ".join(profile[key])),styles["CVBody"]))
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
                "template": data.get("template","classic"),
                "created_at": data.get("created_at",""),
                "ats_score": data.get("ats",{}).get("score"),
            })
        except (OSError,ValueError,TypeError):
            continue
    versions.sort(key=lambda item:item.get("created_at",""),reverse=True)
    return versions[:max(1,min(limit,200))]
