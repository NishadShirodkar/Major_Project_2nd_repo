import React, { useState, useEffect } from "react";
import { artifactService } from "../services/artifactService.js";
import { LoadingState } from "./LoadingState.jsx";

function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function ArtifactList({ caseId }) {
  const [artifacts, setArtifacts] = useState([]);
  const [draftPdfAvailable, setDraftPdfAvailable] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Inspector modal state
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [inspectContent, setInspectContent] = useState(null);
  const [isInspectLoading, setIsInspectLoading] = useState(false);
  const [inspectError, setInspectError] = useState(null);

  const fetchArtifacts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await artifactService.listArtifacts(caseId);
      setArtifacts(data.artifacts || []);
      setDraftPdfAvailable(data.draft_pdf_available || false);
      setIsLoading(false);
    } catch (err) {
      setIsLoading(false);
      setError(err.message || "Failed to retrieve case artifacts.");
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, [caseId]);

  const handleInspectArtifact = async (art) => {
    setSelectedArtifact(art);
    setInspectContent(null);
    setInspectError(null);
    setIsInspectLoading(true);

    try {
      const content = await artifactService.getArtifactContent(caseId, art.name);
      setInspectContent(content);
      setIsInspectLoading(false);
    } catch (err) {
      setIsInspectLoading(false);
      setInspectError(err.message || `Failed to read artifact '${art.name}'.`);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
          </svg>
          Investigation Artifacts Discovery
        </h3>
        <span className="badge badge-neutral">
          {artifacts.filter((a) => a.exists).length} / {artifacts.length} Generated
        </span>
      </div>

      {isLoading ? (
        <LoadingState message="Discovering case artifacts..." />
      ) : error ? (
        <div className="alert alert-danger">{error}</div>
      ) : artifacts.length === 0 ? (
        <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)" }}>
          No artifacts registered for this case.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Artifact Name</th>
                <th>Storage Relative Path</th>
                <th>Size</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((art) => (
                <tr key={art.name}>
                  <td>
                    <div style={{ fontWeight: "600", fontFamily: "var(--font-mono)" }}>
                      {art.name}
                    </div>
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                    {art.relative_path}
                  </td>
                  <td style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                    {art.exists ? formatFileSize(art.size_bytes) : "—"}
                  </td>
                  <td>
                    {art.exists ? (
                      <span className="badge badge-success">READY</span>
                    ) : (
                      <span className="badge badge-neutral">PENDING</span>
                    )}
                  </td>
                  <td>
                    {art.exists && art.relative_path.endsWith(".json") && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleInspectArtifact(art)}
                      >
                        Inspect JSON
                      </button>
                    )}
                    {art.name === "chargesheet_draft" && art.exists && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => artifactService.downloadDraftPdf(caseId)}
                      >
                        Download PDF
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* JSON Inspector Modal */}
      {selectedArtifact && (
        <div className="modal-overlay" onClick={() => setSelectedArtifact(null)}>
          <div
            className="modal-content"
            style={{ maxWidth: "800px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "15px", fontFamily: "var(--font-mono)" }}>
                Artifact Inspector: {selectedArtifact.name}
              </h3>
              <button
                onClick={() => setSelectedArtifact(null)}
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "18px" }}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {isInspectLoading ? (
                <LoadingState message="Loading JSON artifact content..." />
              ) : inspectError ? (
                <div className="alert alert-danger">{inspectError}</div>
              ) : (
                <pre className="json-viewer">
                  {JSON.stringify(inspectContent, null, 2)}
                </pre>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setSelectedArtifact(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
