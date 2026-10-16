import React, { useState, useEffect } from "react";
import { caseService } from "../services/caseService.js";
import { LoadingState, ErrorState, EmptyState } from "../components/LoadingState.jsx";
import CreateCaseModal from "../components/CreateCaseModal.jsx";

export default function DashboardPage({
  onSelectCase,
  onLaunchSimulation,
  refreshSignal,
}) {
  const [cases, setCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const fetchCases = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await caseService.listCases();
      setCases(data.cases || []);
      setIsLoading(false);
    } catch (err) {
      setIsLoading(false);
      setError(err.message || "Failed to load cases from Byomkesh backend.");
    }
  };

  useEffect(() => {
    fetchCases();
  }, [refreshSignal]);

  const handleCaseCreated = (newCase) => {
    fetchCases();
    if (newCase?.case_id) {
      onSelectCase(newCase.case_id);
    }
  };

  const handleDeleteClick = (caseId, e) => {
    if (e) e.stopPropagation();
    setCaseToDelete(caseId);
    setDeleteError(null);
  };

  const handleConfirmDelete = async () => {
    if (!caseToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await caseService.deleteCase(caseToDelete);
      setIsDeleting(false);
      setCaseToDelete(null);
      fetchCases();
    } catch (err) {
      setIsDeleting(false);
      setDeleteError(err.message || `Failed to delete case '${caseToDelete}'.`);
    }
  };

  const filteredCases = cases.filter((c) => {
    const q = searchQuery.toLowerCase();
    return (
      c.case_id.toLowerCase().includes(q) ||
      (c.title && c.title.toLowerCase().includes(q)) ||
      (c.status && c.status.toLowerCase().includes(q))
    );
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case "processed":
        return <span className="badge badge-success">PROCESSED</span>;
      case "documents_uploaded":
        return <span className="badge badge-review-required">DOCS UPLOADED</span>;
      default:
        return <span className="badge badge-neutral">CREATED</span>;
    }
  };

  const getValidationBadge = (disp) => {
    if (!disp) return <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>—</span>;
    const d = disp.toUpperCase();
    if (d === "DRAFT_ALLOWED") return <span className="badge badge-draft-allowed">DRAFT ALLOWED</span>;
    if (d === "REVIEW_REQUIRED") return <span className="badge badge-review-required">REVIEW REQ</span>;
    if (d === "FINAL_BLOCKED") return <span className="badge badge-final-blocked">BLOCKED</span>;
    return <span className="badge badge-neutral">{disp}</span>;
  };

  return (
    <div>
      {/* Top Action Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "20px", fontWeight: "700" }}>
            Investigation Cases
          </h2>
          <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
            Case workspaces, evidence documents, and statutory charge-sheet generation.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            className="btn btn-outline"
            onClick={onLaunchSimulation}
            title="Open 3D Crime Scene Reconstruction Viewer"
            id="dashboard-open-3d-btn"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            </svg>
            3D Crime Scene Viewer
          </button>

          <button
            className="btn btn-primary"
            onClick={() => setIsCreateModalOpen(true)}
            id="create-new-case-btn"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            Create New Case
          </button>
        </div>
      </div>

      {/* Search and Summary */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
          gap: "16px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ width: "320px", maxWidth: "100%" }}>
          <input
            type="text"
            className="form-input"
            placeholder="Search by Case ID, title, or status..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          Showing {filteredCases.length} of {cases.length} case{cases.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <LoadingState message="Loading investigation cases from Byomkesh backend..." />
      ) : error ? (
        <ErrorState
          title="Backend Connection Error"
          message={error}
          onRetry={fetchCases}
        />
      ) : cases.length === 0 ? (
        <EmptyState
          title="No Investigation Cases Found"
          message="There are currently no cases recorded on the Byomkesh AI backend. Create your first case workspace to begin uploading evidence and drafting charge-sheets."
          action={
            <button className="btn btn-primary" onClick={() => setIsCreateModalOpen(true)}>
              Create Your First Case
            </button>
          }
        />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Case Identifier</th>
                  <th>Created Date</th>
                  <th>Evidence Docs</th>
                  <th>Processing Status</th>
                  <th>Validation Disposition</th>
                  <th>Review Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((c) => (
                  <tr
                    key={c.case_id}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelectCase(c.case_id)}
                  >
                    <td>
                      <div style={{ fontWeight: "600", fontFamily: "var(--font-mono)", color: "var(--color-accent)" }}>
                        {c.case_id}
                      </div>
                      {c.title && (
                        <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {c.title}
                        </div>
                      )}
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                      {c.document_count} file{c.document_count !== 1 ? "s" : ""}
                    </td>
                    <td>{getStatusBadge(c.status)}</td>
                    <td>{getValidationBadge(c.validation_disposition)}</td>
                    <td>
                      <span className="badge badge-neutral" style={{ fontSize: "10px" }}>
                        {c.review_status || "created"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onSelectCase(c.case_id)}
                          id={`open-case-${c.case_id}`}
                        >
                          Open &rarr;
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={(e) => handleDeleteClick(c.case_id, e)}
                          title="Permanently delete case workspace"
                          style={{
                            color: "var(--color-danger)",
                            borderColor: "rgba(239, 68, 68, 0.4)",
                            padding: "4px 8px",
                            fontSize: "12px",
                          }}
                          id={`delete-case-${c.case_id}`}
                        >
                          🗑️ Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {caseToDelete && (
        <div className="modal-backdrop">
          <div className="modal-dialog card" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", color: "var(--color-danger)" }}>
                ⚠️ Confirm Case Workspace Deletion
              </h3>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setCaseToDelete(null)}
                disabled={isDeleting}
              >
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ margin: "16px 0" }}>
              <p style={{ margin: "0 0 12px 0", fontSize: "13px", lineHeight: "1.5" }}>
                Are you sure you want to permanently delete investigation case{" "}
                <strong style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent)" }}>
                  {caseToDelete}
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
                <strong>Warning:</strong> This will erase all uploaded evidence files, OCR transcriptions, knowledge graphs, and generated charge-sheet PDFs. This action cannot be undone.
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
                onClick={() => setCaseToDelete(null)}
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

      {/* Create Case Modal */}
      <CreateCaseModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCaseCreated={handleCaseCreated}
      />
    </div>
  );
}
