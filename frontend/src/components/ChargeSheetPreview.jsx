import React, { useState, useEffect } from "react";
import { reviewService } from "../services/reviewService.js";
import { artifactService } from "../services/artifactService.js";
import { LoadingState } from "./LoadingState.jsx";

export default function ChargeSheetPreview({ caseId, reviewStatus: initialStatus, onLaunchSimulation }) {
  const [reviewData, setReviewData] = useState(null);
  const [historyData, setHistoryData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isFinalDownloading, setIsFinalDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Edit Mode State
  const [isEditing, setIsEditing] = useState(false);
  const [editFields, setEditFields] = useState({});
  const [reviewerId, setReviewerId] = useState("");
  const [reviewerName, setReviewerName] = useState("");
  const [correctionComments, setCorrectionComments] = useState("");

  // Modals State
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [showDecisionModal, setShowDecisionModal] = useState(null); // 'approve' | 'reject' | 'request_revision' | 'finalize'
  const [showRetrievalModal, setShowRetrievalModal] = useState(false);
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalResults, setRetrievalResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [retrievalError, setRetrievalError] = useState(null);
  const [noteAuthorId, setNoteAuthorId] = useState("");
  const [noteAuthorName, setNoteAuthorName] = useState("");
  const [noteText, setNoteText] = useState("");
  const [decisionComments, setDecisionComments] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const handleSearchEvidence = async (e) => {
    if (e) e.preventDefault();
    if (!retrievalQuery.trim()) return;
    setIsSearching(true);
    setRetrievalError(null);
    try {
      const res = await reviewService.searchEvidence(caseId, retrievalQuery.trim());
      setRetrievalResults(res);
      setIsSearching(false);
    } catch (err) {
      setIsSearching(false);
      setRetrievalError(err.message || "Failed to search case evidence.");
    }
  };

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await reviewService.getReviewData(caseId);
      setReviewData(data);
      setIsLoading(false);
    } catch (err) {
      setIsLoading(false);
      setError(err.message || "Failed to load charge-sheet review data.");
    }
  };

  useEffect(() => {
    loadData();
  }, [caseId]);

  const loadHistory = async () => {
    try {
      const hist = await reviewService.getHistory(caseId);
      setHistoryData(hist);
      setShowHistoryModal(true);
    } catch (err) {
      setError(err.message || "Failed to load history.");
    }
  };

  const startEditing = () => {
    if (!reviewData?.charge_sheet_data) return;
    const cs = reviewData.charge_sheet_data;
    setEditFields({
      case_summary: cs.case_summary?.value || "",
      detailed_facts: cs.detailed_facts?.value || "",
      investigation_conducted: cs.investigation_conducted?.value || "",
      evidence_analysis: cs.evidence_analysis?.value || "",
      final_opinion: cs.final_opinion?.value || "",
      signature: cs.signature?.value || "",
      court: cs.court?.value || "",
      police_station: cs.police_station?.value || "",
    });
    setReviewerId("");
    setCorrectionComments("");
    setIsEditing(true);
    setActionSuccess(null);
  };

  const handleSaveCorrections = async (e) => {
    e.preventDefault();
    if (!reviewerId.trim()) {
      setError("Reviewer ID / Officer Badge number is required to save corrections.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setActionSuccess(null);
    try {
      const updated = await reviewService.applyCorrections(caseId, {
        reviewer_id: reviewerId.trim(),
        reviewer_name: reviewerName.trim() || undefined,
        comments: correctionComments.trim() || undefined,
        corrections: editFields,
      });
      setReviewData(updated);
      setIsSaving(false);
      setIsEditing(false);
      setActionSuccess(`Corrections successfully recorded as Version ${updated.data_version}. Prior approval invalidated per review rules.`);
    } catch (err) {
      setIsSaving(false);
      setError(err.message || "Failed to save corrections.");
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteAuthorId.trim() || !noteText.trim()) {
      setError("Author ID and observation note text are required.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const updated = await reviewService.addNote(caseId, {
        author_id: noteAuthorId.trim(),
        author_name: noteAuthorName.trim() || undefined,
        note_text: noteText.trim(),
      });
      setReviewData(updated);
      setIsSaving(false);
      setShowNoteModal(false);
      setNoteText("");
      setActionSuccess("Observation note attached to audit trail.");
    } catch (err) {
      setIsSaving(false);
      setError(err.message || "Failed to add note.");
    }
  };

  const handleRecordDecision = async (e) => {
    e.preventDefault();
    if (!reviewerId.trim()) {
      setError("Reviewer ID is required to record this statutory review decision.");
      return;
    }
    if (showDecisionModal === "reject" && !rejectionReason.trim()) {
      setError("A specific rejection reason is mandatory.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const updated = await reviewService.recordDecision(caseId, {
        decision: showDecisionModal,
        reviewer_id: reviewerId.trim(),
        reviewer_name: reviewerName.trim() || undefined,
        comments: decisionComments.trim() || undefined,
        rejection_reason: rejectionReason.trim() || undefined,
      });
      setReviewData(updated);
      setIsSaving(false);
      setShowDecisionModal(null);
      setActionSuccess(`Review decision '${showDecisionModal.toUpperCase()}' successfully executed.`);
    } catch (err) {
      setIsSaving(false);
      setError(err.message || "Failed to record decision.");
    }
  };

  const handleDownloadDraft = async () => {
    setIsDownloading(true);
    setError(null);
    try {
      await artifactService.downloadDraftPdf(caseId);
      setIsDownloading(false);
    } catch (err) {
      setIsDownloading(false);
      setError(err.message || "Failed to download draft PDF.");
    }
  };

  const handleDownloadFinal = async () => {
    setIsFinalDownloading(true);
    setError(null);
    try {
      await artifactService.downloadFinalPdf(caseId);
      setIsFinalDownloading(false);
    } catch (err) {
      setIsFinalDownloading(false);
      setError(err.message || "Failed to download finalized PDF.");
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading charge-sheet review data and provenance..." />;
  }

  const cs = reviewData?.charge_sheet_data;
  const comp = reviewData?.completeness_report;
  const status = reviewData?.status || initialStatus || "draft";
  const isFinalized = reviewData?.is_finalized || status === "finalized";
  const canApprove = reviewData?.can_approve;
  const canFinalize = reviewData?.can_finalize;

  const getStatusBadge = (st) => {
    const s = String(st).toLowerCase();
    if (s === "approved") return <span className="badge badge-approved" id="review-status-badge">APPROVED</span>;
    if (s === "finalized") return <span className="badge badge-finalized" id="review-status-badge">FINALIZED & SIGNED</span>;
    if (s === "rejected") return <span className="badge badge-final-blocked" id="review-status-badge">REJECTED</span>;
    if (s === "review_required") return <span className="badge badge-review-required" id="review-status-badge">REVIEW REQUIRED</span>;
    return <span className="badge badge-neutral" id="review-status-badge">DRAFT</span>;
  };

  const getProvenanceBadge = (field) => {
    if (!field) return null;
    const origin = field.origin || (field.status === "reviewer_corrected" ? "reviewer_corrected" : "extracted");
    if (origin === "reviewer_corrected") {
      return <span className="badge badge-corrected" title={`Corrected by ${field.corrected_by || "Reviewer"}`}>REVIEWER CORRECTED</span>;
    }
    if (origin === "derived") {
      return <span className="badge badge-derived">DERIVED FACT</span>;
    }
    if (field.status === "unavailable") {
      return <span className="badge badge-neutral">UNAVAILABLE</span>;
    }
    if (field.review_required) {
      return <span className="badge badge-review-required">REVIEW REQUIRED</span>;
    }
    return <span className="badge badge-extracted">EXTRACTED</span>;
  };

  const renderFieldValue = (field) => {
    if (!field || field.status === "unavailable" || !field.value) {
      return <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>[Not Available in Investigation Records]</span>;
    }
    return field.value;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Top Banner / Review Chrome */}
      <div
        className="card"
        style={{
          borderLeft: isFinalized ? "4px solid var(--color-success)" : "4px solid var(--color-warning)",
          background: isFinalized ? "rgba(16, 185, 129, 0.05)" : "rgba(245, 158, 11, 0.05)",
          padding: "18px 22px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <span className="badge badge-neutral" style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>
                VERSION {reviewData?.data_version || 1}
              </span>
              {getStatusBadge(status)}
              <span style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.5px" }}>
                CHARGE-SHEET ENGINE (FORM IF-5 / SEC. 193 BNSS)
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
              Case ID: <strong>{caseId}</strong> &bull; Mode: <strong>Evidence-Grounded Legal Provenance</strong>
              {cs?.case_number?.value && <span> &bull; Ref: <strong>{cs.case_number.value}</strong></span>}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <button
              className="btn btn-outline btn-sm"
              onClick={loadHistory}
              id="view-history-btn"
            >
              📜 Audit History ({reviewData?.events?.length || 0})
            </button>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => { setShowRetrievalModal(true); setRetrievalError(null); }}
              id="search-evidence-btn"
            >
              🔍 Search Evidence
            </button>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => { setShowNoteModal(true); setActionSuccess(null); }}
              id="add-note-btn"
            >
              💬 Add Note ({reviewData?.notes?.length || 0})
            </button>
            {!isFinalized && !isEditing && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={startEditing}
                id="edit-chargesheet-btn"
              >
                ✏ Edit Eligible Fields
              </button>
            )}
            {onLaunchSimulation && (
              <button
                className="btn btn-outline btn-sm"
                onClick={onLaunchSimulation}
                id="chargesheet-launch-3d-btn"
                style={{ borderColor: "var(--color-accent)", color: "var(--color-accent)", fontWeight: "600" }}
                title="Open 3D Crime Scene Reconstruction Viewer"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: "5px", verticalAlign: "middle" }}>
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                </svg>
                View 3D Reconstruction of This Case
              </button>
            )}
            {reviewData?.draft_pdf_available && (
              <button
                className="btn btn-primary btn-sm"
                onClick={handleDownloadDraft}
                disabled={isDownloading}
                id="download-draft-pdf-btn"
              >
                {isDownloading ? "Downloading..." : "⬇ Download Draft PDF"}
              </button>
            )}
            {reviewData?.final_pdf_available && (
              <button
                className="btn btn-success btn-sm"
                onClick={handleDownloadFinal}
                disabled={isFinalDownloading}
                id="download-final-pdf-btn"
                style={{ background: "var(--color-success)", color: "#050811", fontWeight: "700" }}
              >
                {isFinalDownloading ? "Downloading..." : "🏆 Download Final Approved PDF"}
              </button>
            )}
          </div>
        </div>

        {/* Success Alert */}
        {actionSuccess && (
          <div className="alert alert-success" style={{ marginTop: "14px", marginBottom: "0" }}>
            ✓ {actionSuccess}
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="alert alert-danger" style={{ marginTop: "14px", marginBottom: "0" }}>
            ✕ {error}
          </div>
        )}
      </div>

      {/* Review Decisions & Guarded Finalization Action Bar */}
      {!isFinalized && !isEditing && (
        <div
          className="card"
          style={{
            background: "var(--bg-surface-elevated)",
            padding: "16px 20px",
            border: "1px solid var(--border-strong)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)" }}>
                Officer Review Decisions & Statutory Gate
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Substantive decisions are logged immutably. Approved revisions revert to review status upon inline modification.
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => { setShowDecisionModal("request_revision"); setReviewerId(""); setDecisionComments(""); }}
                id="decision-revision-btn"
              >
                Request Revision
              </button>

              <button
                className="btn btn-danger btn-sm"
                onClick={() => { setShowDecisionModal("reject"); setReviewerId(""); setRejectionReason(""); }}
                id="decision-reject-btn"
              >
                Reject Draft
              </button>

              <button
                className="btn btn-outline btn-sm"
                onClick={() => { setShowDecisionModal("approve"); setReviewerId(""); setDecisionComments(""); }}
                disabled={!canApprove}
                id="decision-approve-btn"
                title={!canApprove ? "Case disposition prevents approval" : "Approve this draft version"}
              >
                ✓ Approve Draft
              </button>

              <button
                className="btn btn-primary btn-sm"
                onClick={() => { setShowDecisionModal("finalize"); setReviewerId(""); }}
                disabled={!canFinalize}
                id="decision-finalize-btn"
                title={!canFinalize ? "Finalization blocked: requires approval and 0 critical blockers." : "Permanently finalize charge-sheet"}
                style={{
                  background: canFinalize ? "var(--color-success)" : "rgba(100, 116, 139, 0.2)",
                  borderColor: canFinalize ? "var(--color-success)" : "var(--border-subtle)",
                  color: canFinalize ? "#050811" : "var(--text-muted)",
                  fontWeight: "700",
                }}
              >
                🔒 Finalize Charge-Sheet
              </button>
            </div>
          </div>

          {!canFinalize && status === "approved" && comp?.critical_blockers?.length > 0 && (
            <div style={{ marginTop: "12px", fontSize: "12px", color: "var(--color-danger)" }}>
              ⛔ <strong>Finalization Blocked:</strong> {comp.critical_blockers.length} critical blocker(s) unresolved: {comp.critical_blockers.join("; ")}
            </div>
          )}

          {!canFinalize && status !== "approved" && (
            <div style={{ marginTop: "12px", fontSize: "11px", color: "var(--text-muted)" }}>
              ℹ Finalization requires an explicit officer <strong>Approval</strong> decision and zero critical validation blockers.
            </div>
          )}
        </div>
      )}

      {/* Completeness & Readiness Report Card */}
      {comp && (
        <div className="card" style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <h4 style={{ margin: 0, fontSize: "14px", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
              <span>📊</span> Charge-Sheet Statutory Completeness Report
            </h4>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Score: <strong>{Math.round(comp.completeness_score * 100)}%</strong> ({comp.populated_fields_count} / {comp.total_core_fields} fields)
              </span>
              <span className={`badge ${comp.critical_blockers?.length === 0 ? "badge-success" : "badge-final-blocked"}`}>
                {comp.critical_blockers?.length === 0 ? "NO BLOCKERS" : `${comp.critical_blockers.length} CRITICAL BLOCKER(S)`}
              </span>
            </div>
          </div>

          {/* Blockers */}
          {comp.critical_blockers?.length > 0 && (
            <div className="alert alert-danger" style={{ marginBottom: "12px" }}>
              <div>
                <strong>Critical Validation Blockers (Prevents Finalization):</strong>
                <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                  {comp.critical_blockers.map((b, idx) => (
                    <li key={idx}>{b}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Advisory Warnings */}
          {comp.advisory_warnings?.length > 0 && (
            <div className="alert alert-warning" style={{ marginBottom: "0" }}>
              <div>
                <strong>Advisory Procedural Warnings:</strong>
                <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                  {comp.advisory_warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Inline Corrections Form */}
      {isEditing && (
        <form onSubmit={handleSaveCorrections} className="card" style={{ border: "2px solid var(--color-accent)" }}>
          <div className="card-header">
            <h3 className="card-title">
              ✏ Reviewer Correction Workspace (Creating Version {(reviewData?.data_version || 1) + 1})
            </h3>
            <span className="badge badge-corrected">EDIT MODE ACTIVE</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div>
                <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                  Reviewer / Officer ID *
                </label>
                <input
                  type="text"
                  className="input"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="e.g. officer_panaji_44"
                  required
                  id="edit-reviewer-id-input"
                  style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                />
              </div>

              <div>
                <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                  Officer Name & Designation (Optional)
                </label>
                <input
                  type="text"
                  className="input"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  placeholder="e.g. Inspector V. Naik, SDPO"
                  style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Reason / Revision Justification (Audit Comment)
              </label>
              <input
                type="text"
                className="input"
                value={correctionComments}
                onChange={(e) => setCorrectionComments(e.target.value)}
                placeholder="e.g. Rectified factual timeline based on medical report verification"
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
              />
            </div>

            <hr style={{ borderColor: "var(--border-subtle)" }} />

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Case Summary
              </label>
              <textarea
                rows={3}
                value={editFields.case_summary || ""}
                onChange={(e) => setEditFields({ ...editFields, case_summary: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Detailed Facts of Occurrence
              </label>
              <textarea
                rows={4}
                value={editFields.detailed_facts || ""}
                onChange={(e) => setEditFields({ ...editFields, detailed_facts: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Investigation Conducted
              </label>
              <textarea
                rows={3}
                value={editFields.investigation_conducted || ""}
                onChange={(e) => setEditFields({ ...editFields, investigation_conducted: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Evidence Analysis
              </label>
              <textarea
                rows={3}
                value={editFields.evidence_analysis || ""}
                onChange={(e) => setEditFields({ ...editFields, evidence_analysis: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Final Opinion of Investigating Officer
              </label>
              <textarea
                rows={2}
                value={editFields.final_opinion || ""}
                onChange={(e) => setEditFields({ ...editFields, final_opinion: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Officer Signature / Endorsement
              </label>
              <input
                type="text"
                value={editFields.signature || ""}
                onChange={(e) => setEditFields({ ...editFields, signature: e.target.value })}
                style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setIsEditing(false)}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSaving}
                id="save-corrections-submit-btn"
              >
                {isSaving ? "Saving & Re-rendering PDF..." : "Save Corrections & Re-render PDF"}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Main Charge-Sheet Content Display */}
      {cs && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              📋 Form IF-5 Statutory Fields & Provenance
            </h3>
            <span className="badge badge-neutral" style={{ fontFamily: "var(--font-mono)" }}>
              {status.toUpperCase()}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "20px", padding: "16px" }}>
            {/* Case Info Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
              <div style={{ background: "var(--bg-base)", padding: "12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Case Number / FIR</span>
                  {getProvenanceBadge(cs.case_number)}
                </div>
                <div style={{ fontWeight: "600", fontSize: "14px" }}>{renderFieldValue(cs.case_number)}</div>
              </div>

              <div style={{ background: "var(--bg-base)", padding: "12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Police Station</span>
                  {getProvenanceBadge(cs.police_station)}
                </div>
                <div style={{ fontWeight: "600", fontSize: "14px" }}>{renderFieldValue(cs.police_station)}</div>
              </div>

              <div style={{ background: "var(--bg-base)", padding: "12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Jurisdictional Court</span>
                  {getProvenanceBadge(cs.court)}
                </div>
                <div style={{ fontWeight: "600", fontSize: "14px" }}>{renderFieldValue(cs.court)}</div>
              </div>
            </div>

            {/* Case Summary */}
            <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>CASE SUMMARY</span>
                {getProvenanceBadge(cs.case_summary)}
              </div>
              <div style={{ fontSize: "13px", lineHeight: "1.6" }}>{renderFieldValue(cs.case_summary)}</div>
              {cs.case_summary?.origin === "reviewer_corrected" && (
                <div style={{ fontSize: "11px", color: "var(--color-warning)", marginTop: "6px" }}>
                  ✎ Corrected by: {cs.case_summary.corrected_by} {cs.case_summary.corrected_at ? `(${new Date(cs.case_summary.corrected_at).toLocaleString()})` : ""}
                  {cs.case_summary.original_value && <span> | Orig: <i>"{cs.case_summary.original_value}"</i></span>}
                </div>
              )}
            </div>

            {/* Detailed Facts */}
            <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>DETAILED FACTS OF OCCURRENCE</span>
                {getProvenanceBadge(cs.detailed_facts)}
              </div>
              <div style={{ fontSize: "13px", lineHeight: "1.6", whiteSpace: "pre-line" }}>{renderFieldValue(cs.detailed_facts)}</div>
              {cs.detailed_facts?.origin === "reviewer_corrected" && (
                <div style={{ fontSize: "11px", color: "var(--color-warning)", marginTop: "6px" }}>
                  ✎ Corrected by: {cs.detailed_facts.corrected_by} | Orig: <i>"{cs.detailed_facts.original_value}"</i>
                </div>
              )}
            </div>

            {/* Statutory Legal Reasoning & Ingredients Breakdown */}
            <div style={{ background: "var(--bg-base)", padding: "16px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-strong)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--color-accent)" }}>
                  ⚖ STATUTORY OFFENCES & INGREDIENT-LEVEL REASONING
                </span>
                <span className="badge badge-neutral">
                  {cs.legal_findings?.length || 0} SECTION(S) ANALYZED
                </span>
              </div>

              {(!cs.legal_findings || cs.legal_findings.length === 0) ? (
                <div style={{ fontSize: "13px", color: "var(--text-muted)", fontStyle: "italic" }}>
                  No statutory offences established from investigation records.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                  {cs.legal_findings.map((finding, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: "var(--bg-surface)",
                        padding: "14px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
                        <div>
                          <strong style={{ fontSize: "14px", color: "var(--text-primary)" }}>
                            {finding.offence?.value || finding.offence} — {finding.proposed_section?.value || finding.proposed_section}
                          </strong>
                        </div>
                        <div style={{ display: "flex", gap: "6px" }}>
                          <span className={`badge ${finding.status === "supported" ? "badge-success" : (finding.status === "insufficient_evidence" ? "badge-neutral" : "badge-review-required")}`}>
                            STATUS: {String(finding.status).toUpperCase()}
                          </span>
                          <span className="badge badge-neutral">
                            STRENGTH: {String(finding.evidence_strength).toUpperCase()}
                          </span>
                        </div>
                      </div>

                      {finding.reasoning_summary && (
                        <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "10px", lineHeight: "1.5" }}>
                          <strong>Statutory Analysis:</strong> {finding.reasoning_summary}
                        </div>
                      )}

                      {/* Ingredients Assessment List */}
                      {finding.ingredient_assessments?.length > 0 && (
                        <div style={{ marginTop: "10px", marginBottom: "10px" }}>
                          <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "6px" }}>
                            Required Legal Ingredients Assessment
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                            {finding.ingredient_assessments.map((ing, iIdx) => {
                              const ingStatus = ing.status || "REQUIRES_REVIEW";
                              const isSupp = ingStatus === "SUPPORTED";
                              const isNot = ingStatus === "NOT_ESTABLISHED";
                              return (
                                <div
                                  key={iIdx}
                                  style={{
                                    background: "var(--bg-base)",
                                    padding: "8px 12px",
                                    borderRadius: "var(--radius-sm)",
                                    fontSize: "12px",
                                    borderLeft: `3px solid ${isSupp ? "var(--color-success)" : (isNot ? "var(--color-danger)" : "var(--color-warning)")}`,
                                  }}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <strong>{ing.ingredient_name || ing.name}</strong>
                                    <span style={{ fontSize: "10px", fontWeight: "700", color: isSupp ? "var(--color-success)" : (isNot ? "var(--color-danger)" : "var(--color-warning)") }}>
                                      {ingStatus}
                                    </span>
                                  </div>
                                  {ing.reasoning && <div style={{ color: "var(--text-muted)", marginTop: "2px" }}>{ing.reasoning}</div>}

                                  {/* Retrieved Passages Corroboration / Contradiction */}
                                  {ing.retrieved_passages?.length > 0 && (
                                    <div style={{ marginTop: "6px", paddingTop: "6px", borderTop: "1px dashed var(--border-subtle)" }}>
                                      <div style={{ fontSize: "10px", fontWeight: "700", color: "var(--color-accent)", textTransform: "uppercase", marginBottom: "4px" }}>
                                        🔍 Retrieved Excerpts from Case Records ({ing.retrieved_passages.length})
                                      </div>
                                      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                        {ing.retrieved_passages.map((rp, rpIdx) => {
                                          const isContra = rp.relevance_category === "contradicting";
                                          return (
                                            <div
                                              key={rpIdx}
                                              style={{
                                                fontSize: "11px",
                                                background: "var(--bg-surface)",
                                                padding: "6px 8px",
                                                borderRadius: "4px",
                                                borderLeft: `2px solid ${isContra ? "var(--color-danger)" : "var(--color-success)"}`,
                                              }}
                                            >
                                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2px" }}>
                                                <span style={{ fontWeight: "600", color: "var(--text-secondary)" }}>
                                                  📄 {rp.document_name || "Document"} (p. {rp.page_number}{rp.line_range ? `, L${rp.line_range[0]}-${rp.line_range[1]}` : ""})
                                                </span>
                                                <span
                                                  className={`badge ${isContra ? "badge-final-blocked" : "badge-success"}`}
                                                  style={{ fontSize: "9px", padding: "1px 6px" }}
                                                >
                                                  {isContra ? "⚠ CONTRADICTORY" : "✓ CORROBORATING"}
                                                </span>
                                              </div>
                                              <div style={{ fontStyle: "italic", color: "var(--text-primary)" }}>
                                                "{rp.text}"
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Missing Evidence / Warnings */}
                      {finding.missing_evidence?.length > 0 && (
                        <div style={{ fontSize: "11px", color: "var(--color-warning)", marginTop: "6px" }}>
                          ⚠ <strong>Missing Statutory Evidence:</strong> {finding.missing_evidence.join("; ")}
                        </div>
                      )}
                      {finding.review_warnings?.length > 0 && (
                        <div style={{ fontSize: "11px", color: "var(--color-danger)", marginTop: "4px" }}>
                          ▲ <strong>Review Warning:</strong> {finding.review_warnings.join("; ")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Investigation Conducted & Evidence Analysis */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>INVESTIGATION CONDUCTED</span>
                  {getProvenanceBadge(cs.investigation_conducted)}
                </div>
                <div style={{ fontSize: "13px", lineHeight: "1.6", whiteSpace: "pre-line" }}>{renderFieldValue(cs.investigation_conducted)}</div>
              </div>

              <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>EVIDENCE ANALYSIS</span>
                  {getProvenanceBadge(cs.evidence_analysis)}
                </div>
                <div style={{ fontSize: "13px", lineHeight: "1.6", whiteSpace: "pre-line" }}>{renderFieldValue(cs.evidence_analysis)}</div>
              </div>
            </div>

            {/* Final Opinion & Signature */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "16px" }}>
              <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>FINAL OPINION OF INVESTIGATING OFFICER</span>
                  {getProvenanceBadge(cs.final_opinion)}
                </div>
                <div style={{ fontSize: "13px", lineHeight: "1.6" }}>{renderFieldValue(cs.final_opinion)}</div>
              </div>

              <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-secondary)" }}>SIGNATURE / ENDORSEMENT</span>
                  {getProvenanceBadge(cs.signature)}
                </div>
                <div style={{ fontSize: "13px", fontWeight: "600" }}>{renderFieldValue(cs.signature)}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Embedded PDF Viewer */}
      {(reviewData?.draft_pdf_available || reviewData?.final_pdf_available) && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              📄 Charge-Sheet Document Preview ({isFinalized ? "Finalized Official Copy" : "Review Draft"})
            </h3>
            <a
              href={isFinalized ? artifactService.getFinalPdfUrl(caseId) : artifactService.getDraftPdfUrl(caseId)}
              target="_blank"
              rel="noreferrer"
              className="btn btn-outline btn-sm"
              id="open-pdf-window-btn"
            >
              Open in New Window ↗
            </a>
          </div>

          <div
            style={{
              width: "100%",
              height: "650px",
              background: "#05080f",
              borderRadius: "var(--radius-sm)",
              overflow: "hidden",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <iframe
              src={isFinalized ? artifactService.getFinalPdfUrl(caseId) : artifactService.getDraftPdfUrl(caseId)}
              title={`Charge-Sheet ${caseId}`}
              style={{ width: "100%", height: "100%", border: "none" }}
            />
          </div>
        </div>
      )}

      {/* History & Audit Trail Modal */}
      {showHistoryModal && (
        <div className="modal-overlay" onClick={() => setShowHistoryModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "680px" }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>
                📜 Chronological Revision & Decision Audit Trail
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowHistoryModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: "12px", fontSize: "12px", color: "var(--text-secondary)" }}>
                Current Version: <strong>{historyData?.current_version || reviewData?.data_version}</strong> &bull; Total Available Versions: {historyData?.available_versions?.join(", ") || reviewData?.data_version}
              </div>
              {historyData?.events?.length === 0 ? (
                <div style={{ color: "var(--text-muted)" }}>No review events recorded yet.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {historyData?.events?.map((ev, idx) => (
                    <div key={idx} style={{ background: "var(--bg-base)", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <span className="badge badge-neutral" style={{ fontWeight: "700" }}>{String(ev.event_type).toUpperCase()}</span>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{new Date(ev.timestamp).toLocaleString()}</span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        Actor: <strong>{ev.actor_id}</strong> &bull; Version: <strong>v{ev.version}</strong>
                      </div>
                      {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                          {Object.entries(ev.metadata).map(([k, v]) => `${k}: ${v}`).join(" | ")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowHistoryModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Observation Note Modal */}
      {showNoteModal && (
        <div className="modal-overlay" onClick={() => setShowNoteModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleAddNote}>
              <div className="modal-header">
                <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>💬 Attach Review Observation Note</h3>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setShowNoteModal(false)}>✕</button>
              </div>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Author ID / Badge *</label>
                  <input
                    type="text"
                    className="input"
                    value={noteAuthorId}
                    onChange={(e) => setNoteAuthorId(e.target.value)}
                    placeholder="e.g. legal_officer_09"
                    required
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Author Name (Optional)</label>
                  <input
                    type="text"
                    className="input"
                    value={noteAuthorName}
                    onChange={(e) => setNoteAuthorName(e.target.value)}
                    placeholder="e.g. Adv. R. Deshmukh"
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Observation Note Text *</label>
                  <textarea
                    rows={4}
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Enter factual observations, evidentiary discrepancies, or verification requirements..."
                    required
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-sans)" }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowNoteModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={isSaving}>
                  {isSaving ? "Attaching..." : "Attach Note"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Decision Confirmation Modal */}
      {showDecisionModal && (
        <div className="modal-overlay" onClick={() => setShowDecisionModal(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleRecordDecision}>
              <div className="modal-header">
                <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>
                  ⚖ Confirm Decision: {showDecisionModal.toUpperCase()}
                </h3>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setShowDecisionModal(null)}>✕</button>
              </div>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Reviewer Officer ID *</label>
                  <input
                    type="text"
                    className="input"
                    value={reviewerId}
                    onChange={(e) => setReviewerId(e.target.value)}
                    placeholder="e.g. sp_north_goa_01"
                    required
                    id="decision-reviewer-id-input"
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Officer Name (Optional)</label>
                  <input
                    type="text"
                    className="input"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    placeholder="e.g. Superintendent of Police"
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                  />
                </div>

                {showDecisionModal === "reject" && (
                  <div>
                    <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Rejection Reason *</label>
                    <textarea
                      rows={3}
                      value={rejectionReason}
                      onChange={(e) => setRejectionReason(e.target.value)}
                      placeholder="State substantive grounds for rejecting this charge sheet draft..."
                      required
                      style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                    />
                  </div>
                )}

                <div>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>Comments / Endorsement Notes</label>
                  <textarea
                    rows={3}
                    value={decisionComments}
                    onChange={(e) => setDecisionComments(e.target.value)}
                    placeholder="Optional administrative observations or instructions..."
                    style={{ width: "100%", padding: "8px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)" }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowDecisionModal(null)}>Cancel</button>
                <button
                  type="submit"
                  className={`btn ${showDecisionModal === "reject" ? "btn-danger" : "btn-primary"}`}
                  disabled={isSaving}
                  id="confirm-decision-submit-btn"
                >
                  {isSaving ? "Processing..." : `Execute ${showDecisionModal.toUpperCase()}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Evidence Retrieval & Semantic Search Modal */}
      {showRetrievalModal && (
        <div className="modal-overlay" onClick={() => setShowRetrievalModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "760px", maxHeight: "85vh", display: "flex", flexDirection: "column" }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>
                🔍 Case-Isolated Evidence & Passage Search
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowRetrievalModal(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ overflowY: "auto", flex: 1 }}>
              <div style={{ marginBottom: "14px", fontSize: "12px", color: "var(--text-secondary)" }}>
                Query the indexed case documents (OCR passages, witness statements, panchnama, medical and forensic records) with exact document and page-level provenance.
              </div>

              <form onSubmit={handleSearchEvidence} style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
                <input
                  type="text"
                  value={retrievalQuery}
                  onChange={(e) => setRetrievalQuery(e.target.value)}
                  placeholder="Enter investigative query or legal proposition (e.g. 'speed of vehicle', 'head injury', 'brake failure')..."
                  style={{ flex: 1, padding: "9px 12px", background: "var(--bg-base)", border: "1px solid var(--border-strong)", color: "var(--text-primary)", borderRadius: "var(--radius-sm)", fontSize: "13px" }}
                  autoFocus
                />
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isSearching || !retrievalQuery.trim()}
                  id="submit-retrieval-search-btn"
                >
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </form>

              {retrievalError && (
                <div className="alert alert-danger" style={{ marginBottom: "12px" }}>
                  {retrievalError}
                </div>
              )}

              {retrievalResults && (
                <div>
                  <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "8px", display: "flex", justifyContent: "space-between" }}>
                    <span>RESULTS ({retrievalResults.passages?.length || 0})</span>
                    <span>Total Indexed Chunks: {retrievalResults.total_chunks_indexed || 0}</span>
                  </div>

                  {retrievalResults.passages?.length === 0 ? (
                    <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px", background: "var(--bg-base)", borderRadius: "var(--radius-sm)" }}>
                      No matching document passages found above the relevance threshold.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {retrievalResults.passages.map((p, idx) => {
                        const isContra = p.relevance_category === "contradicting";
                        return (
                          <div
                            key={idx}
                            style={{
                              background: "var(--bg-base)",
                              border: "1px solid var(--border-subtle)",
                              borderLeft: `3px solid ${isContra ? "var(--color-danger)" : "var(--color-success)"}`,
                              padding: "12px",
                              borderRadius: "var(--radius-sm)",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                              <span style={{ fontWeight: "700", fontSize: "13px", color: "var(--color-accent)" }}>
                                📄 {p.document_name || "Document"} &bull; Page {p.page_number}
                                {p.line_range ? ` (Lines ${p.line_range[0]}-${p.line_range[1]})` : ""}
                              </span>
                              <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                                  Score: {p.relevance_score}
                                </span>
                                <span className={`badge ${isContra ? "badge-final-blocked" : "badge-success"}`}>
                                  {isContra ? "CONTRADICTING" : "SUPPORTING"}
                                </span>
                              </div>
                            </div>
                            <div style={{ fontSize: "13px", lineHeight: "1.6", color: "var(--text-primary)" }}>
                              "{p.text}"
                            </div>
                            {p.matched_terms?.length > 0 && (
                              <div style={{ marginTop: "6px", fontSize: "11px", color: "var(--text-muted)" }}>
                                Matched terms: {p.matched_terms.join(", ")}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-outline" onClick={() => setShowRetrievalModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
