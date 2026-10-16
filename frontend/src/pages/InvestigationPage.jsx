import React, { useState, useEffect, useRef } from "react";
import { caseService } from "../services/caseService.js";
import { jobService } from "../services/jobService.js";
import { LoadingState, ErrorState } from "../components/LoadingState.jsx";
import DocumentUploader from "../components/DocumentUploader.jsx";
import ProcessingMonitor from "../components/ProcessingMonitor.jsx";
import ValidationPanel from "../components/ValidationPanel.jsx";
import ChargeSheetPreview from "../components/ChargeSheetPreview.jsx";
import ArtifactList from "../components/ArtifactList.jsx";

export default function InvestigationPage({
  caseId,
  onBackToDashboard,
  onLaunchSimulation,
}) {
  const [caseData, setCaseData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Continuous Workflow State: 'intake' | 'processing' | 'review'
  const [workflowState, setWorkflowState] = useState("intake");
  const [activeJobId, setActiveJobId] = useState(null);
  const [isStartingProcess, setIsStartingProcess] = useState(false);
  const [processError, setProcessError] = useState(null);
  const [showEvidenceManager, setShowEvidenceManager] = useState(false);
  const [openDrilldown, setOpenDrilldown] = useState(null); // 'validation' | 'artifacts' | 'metrics'
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const reviewRef = useRef(null);

  const loadCase = async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    setError(null);
    try {
      const data = await caseService.getCase(caseId);
      setCaseData(data);
      if (!isSilent) setIsLoading(false);

      // Determine initial workflow state based on actual backend record
      if (data.status === "processed") {
        setWorkflowState("review");
      } else if (data.active_job_id) {
        setActiveJobId(data.active_job_id);
        setWorkflowState("processing");
      } else {
        setWorkflowState("intake");
      }
    } catch (err) {
      if (!isSilent) setIsLoading(false);
      setError(err.message || `Failed to load details for case '${caseId}'.`);
    }
  };

  useEffect(() => {
    loadCase();
  }, [caseId]);

  // One-Click Pipeline Execution
  const handleStartOneClickProcessing = async () => {
    if (!caseData || caseData.document_count === 0 || isStartingProcess) return;

    setIsStartingProcess(true);
    setProcessError(null);
    setWorkflowState("processing");

    try {
      const res = await jobService.startProcessing(caseId, {
        resume: true, // Reuse cached OCR/parsed artifacts if available
        mock_llm: false, // Real live extraction from uploaded file bytes
      });
      setActiveJobId(res.job_id);
      setIsStartingProcess(false);
    } catch (err) {
      setIsStartingProcess(false);
      setProcessError(err.message || "Failed to trigger automated investigation pipeline.");
    }
  };

  const handleProcessingComplete = async (jobRecord) => {
    // Automatically transition to the Final Charge-Sheet Review page
    await loadCase(true);
    setWorkflowState("review");
    setShowEvidenceManager(false);

    // Smooth scroll to final charge sheet
    setTimeout(() => {
      reviewRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 300);
  };

  const handleUploadSuccess = () => {
    loadCase(true);
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await caseService.deleteCase(caseId);
      setIsDeleting(false);
      setIsDeleteModalOpen(false);
      onBackToDashboard();
    } catch (err) {
      setIsDeleting(false);
      setDeleteError(err.message || `Failed to delete case '${caseId}'.`);
    }
  };

  if (isLoading && !caseData) {
    return <LoadingState message={`Loading investigation workspace for case '${caseId}'...`} />;
  }

  if (error && !caseData) {
    return (
      <div>
        <button className="btn btn-outline btn-sm" onClick={onBackToDashboard} style={{ marginBottom: "16px" }}>
          &larr; Back to Cases
        </button>
        <ErrorState title="Case Retrieval Error" message={error} onRetry={() => loadCase(false)} />
      </div>
    );
  }

  const disposition = caseData?.validation_disposition;
  const isProcessed = caseData?.status === "processed";

  return (
    <div className="investigation-workflow-container">
      {/* Top Breadcrumb & Continuous Journey Action Bar */}
      <div className="case-top-bar">
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <button
            className="btn btn-outline btn-sm"
            onClick={onBackToDashboard}
            id="back-to-dashboard-btn"
          >
            &larr; Cases Dashboard
          </button>
          <span style={{ color: "var(--text-muted)" }}>/</span>
          <span style={{ fontFamily: "var(--font-mono)", fontWeight: "600", fontSize: "14px", color: "var(--color-accent)" }}>
            {caseId}
          </span>
          {isProcessed && (
            <span className="badge badge-success" style={{ marginLeft: "6px" }}>
              CHARGE-SHEET GENERATED
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {/* Prominent 3D Reconstruction Action Button (Part D requirement) */}
          <button
            className="btn btn-outline btn-sm"
            onClick={onLaunchSimulation}
            id="case-launch-3d-btn"
            title="Launch 3D Crime Scene Reconstruction Viewer"
            style={{ borderColor: "var(--color-accent)", color: "var(--color-accent)", fontWeight: "600" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: "5px" }}>
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            </svg>
            View 3D Reconstruction of This Case
          </button>

          {isProcessed && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setShowEvidenceManager(!showEvidenceManager)}
              id="toggle-evidence-mgr-btn"
              title="Add more documents or inspect source files"
            >
              📁 {showEvidenceManager ? "Hide Evidence Intake" : "Manage Evidence Files"}
            </button>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => loadCase(false)}
            title="Refresh case data from server"
            id="case-refresh-btn"
          >
            Refresh
          </button>

          <button
            className="btn btn-outline btn-sm"
            onClick={() => setIsDeleteModalOpen(true)}
            title="Permanently delete this case workspace"
            style={{ color: "var(--color-danger)", borderColor: "rgba(239, 68, 68, 0.4)" }}
            id="case-delete-btn"
          >
            🗑️ Delete Case
          </button>
        </div>
      </div>

      {/* Case Header Card */}
      <div className="card" style={{ marginBottom: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px", flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: "20px", fontWeight: "700" }}>
                {caseData?.title || `Investigation Case ${caseId}`}
              </h2>
              {caseData?.status === "processed" && <span className="badge badge-success">PROCESSED</span>}
              {caseData?.status === "documents_uploaded" && <span className="badge badge-review-required">EVIDENCE STAGED</span>}
              {caseData?.status === "created" && <span className="badge badge-neutral">CREATED</span>}
            </div>

            {caseData?.description && (
              <p style={{ margin: "0 0 8px 0", fontSize: "13px", color: "var(--text-secondary)", maxWidth: "800px" }}>
                {caseData.description}
              </p>
            )}

            <div style={{ fontSize: "12px", color: "var(--text-muted)", display: "flex", gap: "16px", flexWrap: "wrap" }}>
              <span>Case UUID: <strong style={{ fontFamily: "var(--font-mono)" }}>{caseId}</strong></span>
              <span>Evidence Files: <strong>{caseData?.document_count || 0} staged</strong></span>
              <span>Review Status: <strong>{caseData?.review_status || "review_required"}</strong></span>
              <span>Created: <strong>{new Date(caseData?.created_at).toLocaleString()}</strong></span>
            </div>
          </div>

          <div>
            {disposition && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
                  STATUTORY DISPOSITION
                </div>
                <span
                  className={`badge ${
                    disposition === "draft_allowed"
                      ? "badge-draft-allowed"
                      : disposition === "final_blocked"
                      ? "badge-final-blocked"
                      : "badge-review-required"
                  }`}
                  style={{ fontSize: "12px", padding: "5px 12px", letterSpacing: "0.5px" }}
                >
                  {disposition.toUpperCase()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* STAGE 1: EVIDENCE INTAKE (Shown prominently if not yet processed, or toggleable if processed) */}
      {(!isProcessed || showEvidenceManager) && (
        <section className="workflow-section" id="evidence-intake-section" style={{ marginBottom: "24px" }}>
          <div className="section-title-bar">
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
              <span className="step-number">1</span> Evidence Intake &amp; Document Staging
            </h3>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Upload investigation PDFs together: FIR, MLC, Witness Statements, Post-Mortem status, Vehicle Inspection, FSL.
            </span>
          </div>

          <DocumentUploader
            caseId={caseId}
            documents={caseData?.documents || []}
            onUploadSuccess={handleUploadSuccess}
          />

          {/* Prominent One-Click Execution Call To Action */}
          <div className="pipeline-cta-card" style={{ marginTop: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
              <div>
                <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-primary)" }}>
                  Ready to Execute End-to-End Investigation Pipeline?
                </div>
                <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {caseData?.document_count > 0
                    ? `${caseData.document_count} document(s) uploaded. Executes all 9 stages in sequence: OCR &rarr; Parsers &rarr; Graph &rarr; Canonical Facts &rarr; Validation &rarr; RAG &rarr; Legal Reasoning &rarr; Form IF-5 Draft.`
                    : "Upload one or more investigation PDFs above to enable automated pipeline processing."}
                </div>
              </div>

              <button
                className="btn btn-primary btn-lg"
                onClick={handleStartOneClickProcessing}
                disabled={!caseData || caseData.document_count === 0 || isStartingProcess || workflowState === "processing"}
                id="start-investigation-pipeline-btn"
                style={{ minWidth: "260px", padding: "14px 24px", fontSize: "15px", fontWeight: "700" }}
              >
                {isStartingProcess ? (
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="status-dot pulsing"></span> Launching Pipeline...
                  </span>
                ) : (
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    ⚡ Start Investigation Pipeline
                  </span>
                )}
              </button>
            </div>

            {processError && (
              <div className="alert alert-danger" style={{ marginTop: "14px" }}>
                ✕ {processError}
              </div>
            )}
          </div>
        </section>
      )}

      {/* STAGE 2: LIVE PROCESSING MONITOR (Active when processing or job is running) */}
      {(workflowState === "processing" || (activeJobId && !isProcessed)) && (
        <section className="workflow-section" id="pipeline-processing-section" style={{ marginBottom: "24px" }}>
          <div className="section-title-bar">
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
              <span className="step-number">2</span> Live Pipeline Execution &amp; Stage Tracking
            </h3>
            <span style={{ fontSize: "12px", color: "var(--color-accent)" }}>
              Running 9-stage investigation pipeline without tab-switching. Results stream live below.
            </span>
          </div>

          <ProcessingMonitor
            caseId={caseId}
            initialJobId={activeJobId}
            documentCount={caseData?.document_count || 0}
            currentStatus={caseData?.status}
            onProcessingComplete={handleProcessingComplete}
          />
        </section>
      )}

      {/* STAGE 3: FINAL CHARGE-SHEET REVIEW & DRILL-DOWNS (Primary Hero View When Processed) */}
      {isProcessed && (
        <section ref={reviewRef} className="workflow-section" id="chargesheet-review-section">
          <div className="section-title-bar" style={{ marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "17px", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
              <span className="step-number" style={{ background: "var(--color-success)", color: "#000" }}>3</span>
              Final Form IF-5 Charge-Sheet Review &amp; Statutory Assessment
            </h3>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Official charge-sheet draft generated from current case evidence. Review findings, apply officer notes, and download PDF.
            </div>
          </div>

          {/* Main Charge-Sheet Document Component */}
          <ChargeSheetPreview
            caseId={caseId}
            reviewStatus={caseData?.review_status}
            onLaunchSimulation={onLaunchSimulation}
          />

          {/* Drill-Down Accordions Section */}
          <div className="drilldowns-container" style={{ marginTop: "32px" }}>
            <div style={{ marginBottom: "16px" }}>
              <h4 style={{ margin: "0 0 4px 0", fontSize: "15px", fontWeight: "700", color: "var(--text-primary)" }}>
                Deep Forensic Drill-Downs &amp; Evidentiary Findings
              </h4>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--text-secondary)" }}>
                Inspect detailed validation checks, statutory offence ingredients, discovered exhibits, and pipeline metrics.
              </p>
            </div>

            {/* Accordion 1: Evidence Validation & Conflict Detection */}
            <div className="card accordion-card" style={{ marginBottom: "12px" }}>
              <div
                className="accordion-header"
                onClick={() => setOpenDrilldown(openDrilldown === "validation" ? null : "validation")}
                id="accordion-validation-btn"
                style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "16px" }}>⚖️</span>
                  <div>
                    <strong style={{ fontSize: "14px" }}>Evidence Validation &amp; Fact Integrity Analysis</strong>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Contradiction detection across witness statements, missing fact warnings, and statutory disposition.
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="badge badge-neutral">{disposition || "EVALUATED"}</span>
                  <span style={{ fontSize: "14px", color: "var(--text-muted)" }}>
                    {openDrilldown === "validation" ? "▲" : "▼"}
                  </span>
                </div>
              </div>

              {openDrilldown === "validation" && (
                <div className="accordion-body" style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid var(--border-subtle)" }}>
                  <ValidationPanel
                    caseId={caseId}
                    validationDisposition={caseData?.validation_disposition}
                  />
                </div>
              )}
            </div>

            {/* Accordion 2: Discovered Artifacts & Knowledge Graph Entities */}
            <div className="card accordion-card" style={{ marginBottom: "12px" }}>
              <div
                className="accordion-header"
                onClick={() => setOpenDrilldown(openDrilldown === "artifacts" ? null : "artifacts")}
                id="accordion-artifacts-btn"
                style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "16px" }}>📦</span>
                  <div>
                    <strong style={{ fontSize: "14px" }}>Discovered Artifacts &amp; Case Exhibits Directory</strong>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Physical evidence, CCTV records, vehicle inspection results, and storage artifact keys.
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "14px", color: "var(--text-muted)" }}>
                    {openDrilldown === "artifacts" ? "▲" : "▼"}
                  </span>
                </div>
              </div>

              {openDrilldown === "artifacts" && (
                <div className="accordion-body" style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid var(--border-subtle)" }}>
                  <ArtifactList caseId={caseId} />
                </div>
              )}
            </div>

            {/* Accordion 3: Workflow Execution Metrics & Stage History */}
            <div className="card accordion-card" style={{ marginBottom: "12px" }}>
              <div
                className="accordion-header"
                onClick={() => setOpenDrilldown(openDrilldown === "metrics" ? null : "metrics")}
                id="accordion-metrics-btn"
                style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "16px" }}>⚡</span>
                  <div>
                    <strong style={{ fontSize: "14px" }}>Pipeline Execution Details &amp; Processing Metrics</strong>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Execution time per stage, character extraction metrics, confidence scores, and run parameters.
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="badge badge-success">9 STAGES COMPLETED</span>
                  <span style={{ fontSize: "14px", color: "var(--text-muted)" }}>
                    {openDrilldown === "metrics" ? "▲" : "▼"}
                  </span>
                </div>
              </div>

              {openDrilldown === "metrics" && (
                <div className="accordion-body" style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid var(--border-subtle)" }}>
                  <ProcessingMonitor
                    caseId={caseId}
                    initialJobId={activeJobId}
                    documentCount={caseData?.document_count || 0}
                    currentStatus={caseData?.status}
                  />
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Delete Case Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-dialog card" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", color: "var(--color-danger)" }}>
                ⚠️ Confirm Case Workspace Deletion
              </h3>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
              >
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ margin: "16px 0" }}>
              <p style={{ margin: "0 0 12px 0", fontSize: "13px", lineHeight: "1.5" }}>
                Are you sure you want to permanently delete investigation case{" "}
                <strong style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent)" }}>
                  {caseId}
                </strong>
                ?
              </p>
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.08)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: "var(--radius-sm)",
                  padding: "10px 12px",
                  fontSize: "12px",
                  color: "var(--color-danger)",
                }}
              >
                <strong>Warning:</strong> This will erase all uploaded evidence files, OCR transcriptions, knowledge graphs, and generated charge-sheet PDFs for this case. This action cannot be undone.
              </div>

              {deleteError && (
                <div className="alert alert-danger" style={{ marginTop: "12px" }}>
                  <span>{deleteError}</span>
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                className="btn btn-outline"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                id="confirm-delete-case-btn"
                style={{
                  backgroundColor: "var(--color-danger)",
                  borderColor: "var(--color-danger)",
                  color: "#fff",
                  fontWeight: "600",
                }}
              >
                {isDeleting ? "Deleting..." : "Permanently Delete Case"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
