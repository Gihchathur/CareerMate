import { useEffect, useMemo, useState, type FormEvent } from "react";
import { createCandidateEvidence, deleteCandidateEvidence, getCandidateEvidence, updateCandidateEvidence } from "../../api";
import type { CandidateEvidence, CandidateEvidenceInput } from "../../types";
import { Icon } from "../ui/Icon";

const CATEGORY_LABELS: Record<CandidateEvidenceInput["category"], string> = {
  skill: "Skill", experience: "Experience", project: "Project", achievement: "Achievement", education: "Education",
  certification: "Certification", language: "Language", metric: "Measured impact", other: "Other",
};
const SOURCE_LABELS: Record<CandidateEvidenceInput["source_type"], string> = {
  cv: "Source CV", experience: "Work experience", project: "Project", certification: "Certificate", reference: "External reference", manual: "Added manually",
};
const EMPTY_FORM: CandidateEvidenceInput = { claim: "", category: "skill", source_type: "manual", source_reference: "", supporting_detail: "" };

export function EvidenceVault() {
  const [records, setRecords] = useState<CandidateEvidence[]>([]);
  const [form, setForm] = useState<CandidateEvidenceInput>(EMPTY_FORM);
  const [filter, setFilter] = useState<"all" | "verified" | "pending">("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const result = await getCandidateEvidence();
      setRecords(result.evidence);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load candidate evidence.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  const verifiedCount = records.filter((record) => record.verified).length;
  const pendingCount = records.length - verifiedCount;
  const visibleRecords = useMemo(() => records.filter((record) => filter === "all" || (filter === "verified" ? record.verified : !record.verified)), [records, filter]);

  async function addEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const record = await createCandidateEvidence(form);
      setRecords((current) => [record, ...current]);
      setForm(EMPTY_FORM);
      setNotice("Evidence added as pending. Verify it after checking the supporting source.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this evidence.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleVerification(record: CandidateEvidence) {
    try {
      const updated = await updateCandidateEvidence(record.id, { verified: !record.verified });
      setRecords((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(updated.verified ? "Claim marked as verified." : "Claim returned to pending review.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update verification status.");
    }
  }

  async function removeRecord(record: CandidateEvidence) {
    if (!window.confirm("Delete this candidate evidence record? This cannot be undone.")) return;
    try {
      await deleteCandidateEvidence(record.id);
      setRecords((current) => current.filter((item) => item.id !== record.id));
      setNotice("Evidence record deleted.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this evidence.");
    }
  }

  return (
    <section className="cm-evidence-vault cm-card">
      <div className="cm-section-heading cm-evidence-heading">
        <div><span className="cm-kicker">CANDIDATE KNOWLEDGE BASE</span><h3>Evidence vault</h3><p>Keep professional claims connected to the source that supports them. New records are never verified automatically.</p></div>
        <span className="cm-evidence-mark"><Icon name="shield" /></span>
      </div>
      <div className="cm-evidence-summary">
        <div><strong>{records.length}</strong><span>Total claims</span></div>
        <div className="is-verified"><strong>{verifiedCount}</strong><span>Verified</span></div>
        <div className="is-pending"><strong>{pendingCount}</strong><span>Pending review</span></div>
      </div>
      <form className="cm-evidence-form" onSubmit={addEvidence}>
        <div className="cm-evidence-form-heading"><strong>Add a professional claim</strong><small>Use measurable, factual statements where possible.</small></div>
        <label className="cm-evidence-field cm-evidence-wide"><span>Claim</span><input required minLength={3} maxLength={1200} value={form.claim} onChange={(event) => setForm((current) => ({ ...current, claim: event.target.value }))} placeholder="e.g. Reduced notification delivery failures by 25%" /></label>
        <label className="cm-evidence-field"><span>Category</span><select value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value as CandidateEvidenceInput["category"] }))}>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="cm-evidence-field"><span>Supporting source</span><select value={form.source_type} onChange={(event) => setForm((current) => ({ ...current, source_type: event.target.value as CandidateEvidenceInput["source_type"] }))}>{Object.entries(SOURCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="cm-evidence-field"><span>Source reference</span><input maxLength={500} value={form.source_reference} onChange={(event) => setForm((current) => ({ ...current, source_reference: event.target.value }))} placeholder="Company, project, role or CV section" /></label>
        <label className="cm-evidence-field cm-evidence-wide"><span>Supporting detail</span><textarea rows={2} maxLength={4000} value={form.supporting_detail} onChange={(event) => setForm((current) => ({ ...current, supporting_detail: event.target.value }))} placeholder="What did you do, which tools were involved, and how can this claim be checked?" /></label>
        <div className="cm-evidence-form-footer"><span>Stored locally in your CareerMate data folder.</span><button type="submit" className="cm-button cm-button-primary" disabled={saving || !form.claim.trim()}><Icon name="plus" />{saving ? "Saving…" : "Add evidence"}</button></div>
      </form>
      {error && <div className="cm-evidence-message is-error" role="alert">{error}</div>}
      {notice && <div className="cm-evidence-message" role="status">{notice}</div>}
      <div className="cm-evidence-list-heading"><div><strong>Professional claims</strong><small>Verify each claim against a real source before using it in an application.</small></div><div className="cm-evidence-filters" role="group" aria-label="Filter evidence">{(["all", "verified", "pending"] as const).map((value) => <button type="button" key={value} className={filter === value ? "is-active" : ""} onClick={() => setFilter(value)}>{value === "all" ? "All" : value === "verified" ? "Verified" : "Pending"}</button>)}</div></div>
      {loading ? <div className="cm-evidence-empty"><span className="cm-evidence-spinner" /><strong>Loading your evidence…</strong></div> : visibleRecords.length ? <div className="cm-evidence-records">{visibleRecords.map((record, index) => <article className="cm-evidence-record" key={record.id} style={{ animationDelay: `${index * 35}ms` }}>
        <div className={`cm-evidence-status ${record.verified ? "is-verified" : "is-pending"}`}><Icon name={record.verified ? "check" : "clock"} /></div>
        <div className="cm-evidence-record-main"><div className="cm-evidence-tags"><span>{CATEGORY_LABELS[record.category]}</span><span>{SOURCE_LABELS[record.source_type]}</span></div><strong>{record.claim}</strong><small>{[record.source_reference, record.supporting_detail].filter(Boolean).join(" · ") || "No supporting detail added yet."}</small><span className={`cm-evidence-state-label ${record.verified ? "is-verified" : "is-pending"}`}>{record.verified ? "Verified by you" : "Awaiting your verification"}</span></div>
        <div className="cm-evidence-record-actions"><button type="button" onClick={() => void toggleVerification(record)} className={record.verified ? "cm-button cm-button-secondary" : "cm-button cm-button-primary"}>{record.verified ? "Mark pending" : "Verify claim"}</button><button type="button" className="cm-evidence-delete" aria-label={`Delete ${record.claim}`} title="Delete evidence" onClick={() => void removeRecord(record)}><Icon name="trash" /></button></div>
      </article>)}</div> : <div className="cm-evidence-empty"><span><Icon name="file" /></span><strong>{filter === "all" ? "Your evidence vault is empty" : `No ${filter} claims yet`}</strong><p>Add claims with their supporting source. This creates a reviewable foundation for more reliable CV tailoring and job applications.</p></div>}
      <div className="cm-evidence-disclaimer"><Icon name="info" /><span>Verification means you have reviewed the claim and its source. CareerMate does not independently validate employment history, qualifications or metrics.</span></div>
    </section>
  );
}
