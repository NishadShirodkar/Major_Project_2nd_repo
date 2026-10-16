import React, { useState, useRef } from "react";
import { caseService } from "../services/caseService.js";

const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".mp4", ".mov", ".wav"];
const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DocumentUploader({ caseId, documents = [], onUploadSuccess }) {
  const [pendingFiles, setPendingFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadResults, setUploadResults] = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleFilesSelected = (newFiles) => {
    setUploadError(null);
    setUploadResults(null);
    const validFiles = [];
    const rejectedErrors = [];

    Array.from(newFiles).forEach((file) => {
      const ext = `.${file.name.split(".").pop().toLowerCase()}`;
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        rejectedErrors.push(`"${file.name}": Unsupported file extension ${ext}. Allowed: ${ACCEPTED_EXTENSIONS.join(", ")}`);
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejectedErrors.push(`"${file.name}": Exceeds maximum size limit of 100 MB (${formatFileSize(file.size)}).`);
        return;
      }
      // Check if duplicate in pending
      if (pendingFiles.some((f) => f.name === file.name && f.size === file.size)) {
        return;
      }
      validFiles.push(file);
    });

    if (rejectedErrors.length > 0) {
      setUploadError(rejectedErrors.join("\n"));
    }

    setPendingFiles((prev) => [...prev, ...validFiles]);
  };

  const handleRemovePending = (index) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  const handleUploadSubmit = async () => {
    if (pendingFiles.length === 0 || isUploading) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadResults(null);

    try {
      const response = await caseService.uploadDocuments(caseId, pendingFiles);
      setUploadResults(response);
      setPendingFiles([]);
      setIsUploading(false);
      if (onUploadSuccess) {
        onUploadSuccess(response);
      }
    } catch (err) {
      setIsUploading(false);
      setUploadError(err.message || "Failed to upload documents.");
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
          </svg>
          Evidence Document Intake
        </h3>
        <span className="badge badge-neutral">
          {documents.length} Staged Document{documents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Drag & Drop Area */}
      <div
        className={`dropzone ${isDragActive ? "active" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.docx,.mp4,.mov,.wav"
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) handleFilesSelected(e.target.files);
            e.target.value = "";
          }}
        />
        <div style={{ color: "var(--color-accent)", marginBottom: "8px" }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 16 12 12 8 16"></polyline>
            <line x1="12" y1="12" x2="12" y2="21"></line>
            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
            <polyline points="16 16 12 12 8 16"></polyline>
          </svg>
        </div>
        <div style={{ fontWeight: "600", fontSize: "14px", marginBottom: "4px" }}>
          Drop forensic case files here or click to browse
        </div>
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          Supported: PDF, JPG, PNG, DOCX, MP4, MOV, WAV (Max 100 MB per file)
        </div>
      </div>

      {uploadError && (
        <div className="alert alert-danger" style={{ marginTop: "16px", whiteSpace: "pre-line" }}>
          {uploadError}
        </div>
      )}

      {/* Pending Files List */}
      {pendingFiles.length > 0 && (
        <div style={{ marginTop: "20px" }}>
          <div style={{ fontSize: "13px", fontWeight: "600", marginBottom: "10px", color: "var(--text-secondary)" }}>
            Pending Upload Queue ({pendingFiles.length} file{pendingFiles.length !== 1 ? "s" : ""}):
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {pendingFiles.map((file, idx) => (
              <div
                key={`${file.name}_${idx}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  background: "var(--bg-base)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "13px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px", overflow: "hidden" }}>
                  <span style={{ color: "var(--color-accent)", fontFamily: "var(--font-mono)" }}>📄</span>
                  <span style={{ fontWeight: "500", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                    {file.name}
                  </span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px", fontFamily: "var(--font-mono)" }}>
                    ({formatFileSize(file.size)})
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  style={{ padding: "2px 8px", color: "var(--color-danger)" }}
                  onClick={() => handleRemovePending(idx)}
                  disabled={isUploading}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <div style={{ marginTop: "14px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => setPendingFiles([])}
              disabled={isUploading}
            >
              Clear Queue
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUploadSubmit}
              disabled={isUploading}
              id="upload-evidence-btn"
            >
              {isUploading ? (
                <>
                  <span className="status-dot" style={{ backgroundColor: "#030712", animation: "spin 1s linear infinite" }} />
                  Uploading to Case Workspace...
                </>
              ) : (
                `Upload ${pendingFiles.length} File${pendingFiles.length !== 1 ? "s" : ""}`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Upload Results Summary */}
      {uploadResults && (
        <div
          className={`alert ${uploadResults.failed_count > 0 ? "alert-warning" : "alert-success"}`}
          style={{ marginTop: "16px" }}
        >
          <div>
            <strong>Upload Complete:</strong> {uploadResults.uploaded_count} file(s) staged successfully
            {uploadResults.failed_count > 0 && ` (${uploadResults.failed_count} rejected)`}.
          </div>
        </div>
      )}

      {/* Already Uploaded Documents Inventory */}
      <div style={{ marginTop: "24px" }}>
        <h4 style={{ fontSize: "13px", color: "var(--text-secondary)", margin: "0 0 10px 0", textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Current Case Evidence Inventory ({documents.length})
        </h4>

        {documents.length === 0 ? (
          <div style={{ padding: "16px", background: "var(--bg-base)", borderRadius: "var(--radius-sm)", color: "var(--text-muted)", fontSize: "13px", textAlign: "center" }}>
            No evidence documents staged yet. Upload police records, FIR, complaints, or medical reports above.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Original Document</th>
                  <th>Format / Media</th>
                  <th>Size</th>
                  <th>Uploaded Date</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ color: "var(--color-accent)" }}>📁</span>
                        <span style={{ fontWeight: "500", fontFamily: "var(--font-mono)" }}>
                          {doc.original_filename}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral" style={{ fontSize: "10px" }}>
                        {doc.media_type}
                      </span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-secondary)" }}>
                      {formatFileSize(doc.size_bytes)}
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      {new Date(doc.uploaded_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
