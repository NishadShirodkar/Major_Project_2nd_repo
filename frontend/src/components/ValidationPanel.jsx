import React, { useState, useEffect } from "react";
import { artifactService } from "../services/artifactService.js";
import { LoadingState } from "./LoadingState.jsx";

export default function ValidationPanel({ caseId, validationDisposition }) {
  const [reportData, setReportData] = useState(null);
  const [legalData, setLegalData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    Promise.allSettled([
      artifactService.getArtifactContent(caseId, "validation_report"),
      artifactService.getArtifactContent(caseId, "legal_findings"),
    ]).then(([valRes, legalRes]) => {
      if (!isMounted) return;
      setIsLoading(false);

      if (valRes.status === "fulfilled") {
        setReportData(valRes.value);
      }
      if (legalRes.status === "fulfilled") {
        setLegalData(legalRes.value);
      }
      if (valRes.status === "rejected" && legalRes.status === "rejected") {
        setError("Validation reports and legal findings are not available yet. Process the case first.");
      }
    });

    return () => {
      isMounted = false;
    };
  }, [caseId]);

  const disposition = validationDisposition || reportData?.disposition || "PENDING";
  const normalizedDisp = String(disposition).toUpperCase();

  const getDispositionBadge = () => {
    if (normalizedDisp === "DRAFT_ALLOWED") {
      return (
        <span className="badge badge-draft-allowed" style={{ fontSize: "13px", padding: "6px 12px" }}>
          ⚖ DRAFT ALLOWED (REVIEW REQUIRED)
        </span>
      );
    }
    if (normalizedDisp === "REVIEW_REQUIRED") {
      return (
        <span className="badge badge-review-required" style={{ fontSize: "13px", padding: "6px 12px" }}>
          ⚠ MANUAL REVIEW REQUIRED
        </span>
      );
    }
    if (normalizedDisp === "FINAL_BLOCKED") {
      return (
        <span className="badge badge-final-blocked" style={{ fontSize: "13px", padding: "6px 12px" }}>
          ⛔ FINAL DRAFT BLOCKED
        </span>
      );
    }
    return (
      <span className="badge badge-neutral" style={{ fontSize: "13px", padding: "6px 12px" }}>
        PENDING EVALUATION
      </span>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Disposition Card */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            Evidence Validation Disposition
          </h3>
          <div>{getDispositionBadge()}</div>
        </div>

        <div className="alert alert-info" style={{ marginBottom: "16px" }}>
          <div>
            <strong>Legal Notice:</strong> <code>DRAFT_ALLOWED</code> signifies that automated structural validation
            checks have passed to permit drafting inspection. It does <strong>not</strong> constitute final legal or
            judicial approval under Bharatiya Nagarik Suraksha Sanhita (BNSS) or CrPC. Professional supervisory
            verification remains mandatory.
          </div>
        </div>

        {isLoading ? (
          <LoadingState message="Retrieving validation report and legal findings from case artifacts..." />
        ) : error && !reportData && !legalData ? (
          <div className="alert alert-warning">{error}</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
            <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Completeness Score</div>
              <div style={{ fontSize: "24px", fontWeight: "700", fontFamily: "var(--font-mono)", color: "var(--color-accent)", marginTop: "4px" }}>
                {reportData?.completeness_score !== undefined
                  ? `${Math.round(reportData.completeness_score * 100)}%`
                  : "N/A"}
              </div>
            </div>

            <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Validation Rule Violations</div>
              <div style={{ fontSize: "24px", fontWeight: "700", fontFamily: "var(--font-mono)", color: (reportData?.violations?.length || 0) > 0 ? "var(--color-danger)" : "var(--color-success)", marginTop: "4px" }}>
                {reportData?.violations?.length ?? 0}
              </div>
            </div>

            <div style={{ background: "var(--bg-base)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Recommended Charges (BNS)</div>
              <div style={{ fontSize: "24px", fontWeight: "700", fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginTop: "4px" }}>
                {legalData?.recommended_sections?.length || legalData?.charges?.length || 0}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Validation Findings & Rules */}
      {reportData && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Validation Findings & Contradiction Checks</h3>
          </div>

          {reportData.violations && reportData.violations.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
              {reportData.violations.map((v, i) => (
                <div key={i} className="alert alert-danger" style={{ margin: 0 }}>
                  <strong>Rule Violation:</strong> {v.message || JSON.stringify(v)}
                </div>
              ))}
            </div>
          ) : (
            <div className="alert alert-success" style={{ marginBottom: "16px" }}>
              ✓ No fatal evidentiary contradictions or missing mandatory documents detected.
            </div>
          )}

          {reportData.rule_results && (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Rule Identifier</th>
                    <th>Status</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(reportData.rule_results).map(([rule, res]) => (
                    <tr key={rule}>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: "500" }}>{rule}</td>
                      <td>
                        <span className={`badge ${res?.passed ? "badge-success" : "badge-final-blocked"}`}>
                          {res?.passed ? "PASSED" : "FAILED"}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        {res?.message || (res?.passed ? "Satisfied requirements" : "Non-compliant")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Legal Findings Section */}
      {legalData && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              Legal Reasoning & Penal Code Alignment
            </h3>
          </div>

          {legalData.reasoning_summary && (
            <div style={{ background: "var(--bg-base)", padding: "16px", borderRadius: "var(--radius-sm)", marginBottom: "16px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "6px" }}>
                INVESTIGATIVE LEGAL SUMMARY
              </div>
              <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "var(--text-primary)" }}>
                {legalData.reasoning_summary}
              </p>
            </div>
          )}

          {(legalData.recommended_sections || legalData.charges) && (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Statute & Section</th>
                    <th>Offence Description</th>
                    <th>Ingredients Satisfied</th>
                  </tr>
                </thead>
                <tbody>
                  {(legalData.recommended_sections || legalData.charges || []).map((sec, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: "600", color: "var(--color-accent)" }}>
                        {sec.section_code || sec.section || sec.code || `Section ${idx + 1}`}
                      </td>
                      <td style={{ fontWeight: "500" }}>
                        {sec.title || sec.offence || "Offence under BNS/IPC"}
                      </td>
                      <td>
                        <span className="badge badge-success">
                          {sec.ingredients_satisfied !== undefined
                            ? `${sec.ingredients_satisfied} Ingredient(s) Substantiated`
                            : "Substantiated by Evidence"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
