import React, { useState } from "react";
import { caseService } from "../services/caseService.js";

export default function CreateCaseModal({ isOpen, onClose, onCaseCreated }) {
  const [caseId, setCaseId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const payload = {};
    if (caseId.trim()) payload.case_id = caseId.trim();
    if (title.trim()) payload.title = title.trim();
    if (description.trim()) payload.description = description.trim();

    try {
      const response = await caseService.createCase(payload);
      setIsSubmitting(false);
      onCaseCreated(response);
      onClose();
    } catch (err) {
      setIsSubmitting(false);
      setError(err.message || "Failed to create case.");
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ margin: 0, fontSize: "16px", color: "var(--text-primary)" }}>
            Create Investigation Case
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "18px",
            }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="alert alert-danger" style={{ marginBottom: "16px" }}>
                <span>{error}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="case-id-input">
                Case Identifier (Optional)
              </label>
              <input
                id="case-id-input"
                className="form-input"
                type="text"
                placeholder="e.g. CR-2026-089-CENTRAL (leave blank to auto-generate)"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                disabled={isSubmitting}
                maxLength={64}
              />
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                1-64 alphanumeric, dash, or underscore characters.
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="case-title-input">
                Case Title
              </label>
              <input
                id="case-title-input"
                className="form-input"
                type="text"
                placeholder="e.g. Investigation into Market Road Traffic Incident"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isSubmitting}
                maxLength={256}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="case-desc-input">
                Investigation Summary / Notes
              </label>
              <textarea
                id="case-desc-input"
                className="form-textarea"
                rows={3}
                placeholder="Brief description of the FIR, incident details, and preliminary investigative lead."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isSubmitting}
                maxLength={2048}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              id="submit-create-case-btn"
            >
              {isSubmitting ? "Creating Case..." : "Create Case"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
