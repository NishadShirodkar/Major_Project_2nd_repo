import React, { useState, useEffect, useRef } from "react";
import { jobService, PIPELINE_STAGES } from "../services/jobService.js";

export default function ProcessingMonitor({
  caseId,
  initialJobId = null,
  documentCount = 0,
  currentStatus,
  onProcessingComplete,
}) {
  const [jobId, setJobId] = useState(initialJobId);
  const [jobData, setJobData] = useState(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [mockLlmMode, setMockLlmMode] = useState(false); // Default false for real live-file processing
  const [resumeMode, setResumeMode] = useState(true);
  const [pollError, setPollError] = useState(null);

  const pollTimerRef = useRef(null);
  const activeCaseRef = useRef(caseId);

  // Auto-connect to initialJobId if passed
  useEffect(() => {
    if (initialJobId && initialJobId !== jobId) {
      setJobId(initialJobId);
      startPolling(initialJobId);
    }
  }, [initialJobId]);

  // Keep track of caseId to prevent stale polling updates across case switches
  useEffect(() => {
    activeCaseRef.current = caseId;
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [caseId]);

  const handleStartProcessing = async () => {
    if (documentCount === 0 || isTriggering) return;
    setIsTriggering(true);
    setPollError(null);
    setJobData(null);

    try {
      const res = await jobService.startProcessing(caseId, {
        resume: resumeMode,
        mock_llm: mockLlmMode,
      });
      setJobId(res.job_id);
      setIsTriggering(false);
      startPolling(res.job_id);
    } catch (err) {
      setIsTriggering(false);
      setPollError(err.message || "Failed to trigger investigation workflow.");
    }
  };

  const startPolling = (targetJobId) => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
    }

    const poll = async () => {
      // Guard against stale polling if case has switched
      if (activeCaseRef.current !== caseId) return;

      try {
        const data = await jobService.getJob(targetJobId);
        if (activeCaseRef.current !== caseId) return;

        setJobData(data);
        setPollError(null);

        if (data.status === "completed") {
          if (onProcessingComplete) onProcessingComplete(data);
          return; // Stop polling
        }

        if (data.status === "failed") {
          return; // Stop polling on failure
        }

        // Schedule next poll
        pollTimerRef.current = setTimeout(poll, 1500);
      } catch (err) {
        if (activeCaseRef.current !== caseId) return;
        if (err.status === 404) {
          setPollError("Background worker connection closed or server restarted. You can resume processing below.");
          setJobData(null);
          setIsTriggering(false);
          return;
        }
        setPollError(`Job polling interrupted: ${err.message}. Retrying...`);
        pollTimerRef.current = setTimeout(poll, 3000);
      }
    };

    poll();
  };

  // Map backend stage records to the 9 pipeline stages
  const getStageStatus = (stageId) => {
    if (!jobData) {
      if (currentStatus === "processed") return { status: "completed" };
      return { status: "pending" };
    }

    // 1. If completed_stages explicitly has this stage, it is finished
    if (jobData.completed_stages?.includes(stageId)) {
      return { status: "completed" };
    }

    // 2. If current_stage matches, it is actively in progress
    if (jobData.current_stage === stageId) {
      return { status: "running" };
    }

    // 3. Check detailed stage_records if present
    const rec = jobData.stage_records?.find((r) => r.stage_name === stageId);
    if (rec) {
      return { status: rec.status, error: rec.error_message };
    }

    // 4. In-flight fallback based on sequential stage index
    if (jobData.status === "running") {
      const completedCount = jobData.completed_stages?.length || 0;
      const stageIdx = PIPELINE_STAGES.findIndex((s) => s.id === stageId);
      if (stageIdx === completedCount) {
        return { status: "running" };
      }
    }

    return { status: "pending" };
  };

  const isJobActive = jobData?.status === "queued" || jobData?.status === "running" || isTriggering;

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          Investigation Processing & 9-Stage Pipeline
        </h3>

        <div>
          {jobData?.status === "running" && (
            <span className="badge badge-draft-allowed">
              <span className="status-dot" style={{ backgroundColor: "#38bdf8", animation: "spin 1s linear infinite" }} />
              RUNNING PIPELINE
            </span>
          )}
          {jobData?.status === "queued" && (
            <span className="badge badge-review-required">
              QUEUED
            </span>
          )}
          {jobData?.status === "completed" && (
            <span className="badge badge-success">
              ✓ COMPLETED
            </span>
          )}
          {jobData?.status === "failed" && (
            <span className="badge badge-final-blocked">
              ⚠ WORKFLOW FAILED
            </span>
          )}
        </div>
      </div>

      {/* Control Panel */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          padding: "16px",
          background: "var(--bg-base)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border-subtle)",
          marginBottom: "20px",
        }}
      >
        <div>
          <div style={{ fontSize: "14px", fontWeight: "600", marginBottom: "4px" }}>
            Pipeline Workflow Execution
          </div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Executes OCR, entity extraction, canonical synthesis, validation, legal reasoning, and draft charge-sheet compilation.
          </div>
          <div style={{ display: "flex", gap: "16px", marginTop: "10px" }}>
            <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={mockLlmMode}
                onChange={(e) => setMockLlmMode(e.target.checked)}
                disabled={isJobActive}
              />
              <span style={{ color: "var(--text-secondary)" }}>Deterministic Mock LLM</span>
              <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>(offline execution without Gemini key)</span>
            </label>
            <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={resumeMode}
                onChange={(e) => setResumeMode(e.target.checked)}
                disabled={isJobActive}
              />
              <span style={{ color: "var(--text-secondary)" }}>Reuse Cached OCR</span>
            </label>
          </div>
          {mockLlmMode && (
            <div
              style={{
                marginTop: "10px",
                padding: "8px 12px",
                backgroundColor: "rgba(245, 158, 11, 0.12)",
                border: "1px solid rgba(245, 158, 11, 0.4)",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                color: "#f59e0b",
              }}
            >
              ⚠️ <strong>Mock Mode Active:</strong> Running with offline test simulation. Uncheck this box to process actual document contents with the live engine.
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            className="btn btn-primary"
            onClick={handleStartProcessing}
            disabled={documentCount === 0 || isJobActive}
            id="start-processing-btn"
          >
            {isJobActive ? (
              <>
                <span className="status-dot" style={{ backgroundColor: "#030712", animation: "spin 1s linear infinite" }} />
                {jobData?.status === "running" ? "Processing Case..." : "Queuing Job..."}
              </>
            ) : (
              "Start Investigation Processing"
            )}
          </button>
          {isJobActive && (
            <button
              className="btn btn-outline btn-sm"
              style={{ fontSize: "11px", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
              onClick={async () => {
                if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
                try {
                  await jobService.resetProcessing(caseId);
                } catch {
                  // Ignore error during forced reset
                }
                setIsTriggering(false);
                setJobData(null);
                setPollError(null);
              }}
              title="Release processing lock and reset controls"
            >
              Reset Controls
            </button>
          )}
        </div>
      </div>

      {documentCount === 0 && (
        <div className="alert alert-warning">
          <span>Upload at least one case evidence document above before starting the investigation pipeline.</span>
        </div>
      )}

      {pollError && (
        <div className="alert alert-danger" style={{ marginBottom: "16px" }}>
          <span>{pollError}</span>
        </div>
      )}

      {jobData?.error && (
        <div className="alert alert-danger" style={{ marginBottom: "16px" }}>
          <strong>Workflow Failure:</strong> {jobData.error}
        </div>
      )}

      {/* Progress Disclaimer Note */}
      <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "14px", fontStyle: "italic" }}>
        * Note: The backend engine reports authoritative stage-level milestones upon stage completion. Sub-operation percentages are not simulated.
      </div>

      {/* 9-Stage Stepper */}
      <div className="stepper-container">
        {PIPELINE_STAGES.map((stage, idx) => {
          const { status, error } = getStageStatus(stage.id);

          return (
            <div key={stage.id} className={`stepper-stage ${status}`}>
              <div className="stage-info">
                <div className="stage-number">{idx + 1}</div>
                <div>
                  <div style={{ fontWeight: "600", fontSize: "13px", color: "var(--text-primary)" }}>
                    {stage.name}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {stage.description}
                  </div>
                  {error && (
                    <div style={{ fontSize: "11px", color: "var(--color-danger)", marginTop: "2px" }}>
                      Error: {error}
                    </div>
                  )}
                </div>
              </div>

              <div>
                {status === "completed" && (
                  <span className="badge badge-success" style={{ fontSize: "10px" }}>
                    ✓ COMPLETED
                  </span>
                )}
                {status === "running" && (
                  <span className="badge badge-draft-allowed" style={{ fontSize: "10px" }}>
                    IN PROGRESS
                  </span>
                )}
                {status === "failed" && (
                  <span className="badge badge-final-blocked" style={{ fontSize: "10px" }}>
                    FAILED
                  </span>
                )}
                {status === "pending" && (
                  <span className="badge badge-neutral" style={{ fontSize: "10px" }}>
                    PENDING
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
