import React from "react";

export default function LandingPage({
  onGoToLogin,
  onGoToWorkspace,
  isAuthenticated,
  currentOfficer,
}) {
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-container">
          <div className="landing-badge">
            <span className="landing-badge-dot"></span>
            STATUTORY BNS (2023) & FORM IF-5 COMPLIANT FORENSIC ENGINE
          </div>

          <h1 className="landing-title">
            Autonomous Investigation Intelligence &amp; Charge-Sheet System
          </h1>

          <p className="landing-subtitle">
            Transform heterogeneous police case records into verified knowledge graphs,
            conduct ingredient-level statutory legal analysis under the Bharatiya Nyaya Sanhita,
            and generate court-ready Form IF-5 charge sheets with verifiable source provenance.
          </p>

          <div className="landing-actions">
            {isAuthenticated ? (
              <button
                className="btn btn-primary btn-lg"
                onClick={onGoToWorkspace}
                id="landing-enter-workspace-btn"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="7" height="7"></rect>
                  <rect x="14" y="3" width="7" height="7"></rect>
                  <rect x="14" y="14" width="7" height="7"></rect>
                  <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
                Enter Cases Workspace ({currentOfficer?.name || "Officer"})
              </button>
            ) : (
              <>
                <button
                  className="btn btn-primary btn-lg"
                  onClick={onGoToLogin}
                  id="landing-login-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                    <polyline points="10 17 15 12 10 7"></polyline>
                    <line x1="15" y1="12" x2="3" y2="12"></line>
                  </svg>
                  Investigator Sign In
                </button>

                <button
                  className="btn btn-outline btn-lg"
                  onClick={onGoToLogin}
                  id="landing-get-started-btn"
                >
                  Access Case Portal &rarr;
                </button>
              </>
            )}
          </div>

          {/* Quick Metrics Bar */}
          <div className="landing-metrics">
            <div className="landing-metric-item">
              <div className="metric-val">9 Stages</div>
              <div className="metric-lbl">Deterministic Pipeline</div>
            </div>
            <div className="landing-metric-divider"></div>
            <div className="landing-metric-item">
              <div className="metric-val">Form IF-5</div>
              <div className="metric-lbl">Statutory Charge-Sheet</div>
            </div>
            <div className="landing-metric-divider"></div>
            <div className="landing-metric-item">
              <div className="metric-val">Case Isolated</div>
              <div className="metric-lbl">Multi-Evidence RAG</div>
            </div>
            <div className="landing-metric-divider"></div>
            <div className="landing-metric-item">
              <div className="metric-val">100% Provenance</div>
              <div className="metric-lbl">Source-Anchored Facts</div>
            </div>
          </div>
        </div>
      </section>

      {/* Real Core Capabilities Grid */}
      <section className="landing-features-section">
        <div className="landing-container">
          <div className="section-header">
            <div className="section-eyebrow">VERIFIED ARCHITECTURE</div>
            <h2 className="section-title">Forensic Intelligence Across Every Investigation Stage</h2>
            <p className="section-desc">
              Byomkesh AI executes a continuous nine-stage pipeline without fabricating case data or relying on synthetic fallbacks.
            </p>
          </div>

          <div className="features-grid">
            {/* Feature 1 */}
            <div className="feature-card">
              <div className="feature-icon">📁</div>
              <h3 className="feature-title">Multi-Document Evidence Intake</h3>
              <p className="feature-desc">
                Stage 1 &amp; 2: Ingests digital and scanned FIRs, MLC medical reports, post-mortem status certificates,
                witness statements, seizure memos, site plans, vehicle inspection reports, and CCTV analyses into isolated case storage.
              </p>
              <div className="feature-tags">
                <span className="tag">Deterministic Hashing</span>
                <span className="tag">UUID Storage</span>
                <span className="tag">Intake Manifest</span>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="feature-card">
              <div className="feature-icon">🕸️</div>
              <h3 className="feature-title">Knowledge Graph &amp; Entity Normalization</h3>
              <p className="feature-desc">
                Stage 3, 4 &amp; 5: Parses typed investigation domain schemas, constructs a multi-entity knowledge graph,
                and projects canonical facts for persons, roles, vehicles, exhibits, and incident timestamps.
              </p>
              <div className="feature-tags">
                <span className="tag">Typed Parsers</span>
                <span className="tag">Canonical Facts</span>
                <span className="tag">Entity Disambiguation</span>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="feature-card">
              <div className="feature-icon">⚖️</div>
              <h3 className="feature-title">Evidence Validation &amp; Conflict Detection</h3>
              <p className="feature-desc">
                Stage 6: Evaluates evidentiary consistency across witness statements, medical evidence, and seizure memos.
                Computes statutory disposition: Draft Allowed, Review Required, or Final Blocked.
              </p>
              <div className="feature-tags">
                <span className="tag">Witness Contradiction</span>
                <span className="tag">Missing Medical Flags</span>
                <span className="tag">Disposition Rules</span>
              </div>
            </div>

            {/* Feature 4 */}
            <div className="feature-card">
              <div className="feature-icon">🔍</div>
              <h3 className="feature-title">Case-Isolated RAG &amp; Statutory Reasoning</h3>
              <p className="feature-desc">
                Stage 7 &amp; 8: Indexes chunked evidence into a dedicated case index. Evaluates statutory offences under
                the Bharatiya Nyaya Sanhita (BNS 2023) against required ingredients with retrieved source citations.
              </p>
              <div className="feature-tags">
                <span className="tag">Zero Cross-Case Leakage</span>
                <span className="tag">Ingredient Matching</span>
                <span className="tag">BNS 2023</span>
              </div>
            </div>

            {/* Feature 5 */}
            <div className="feature-card">
              <div className="feature-icon">📜</div>
              <h3 className="feature-title">Court-Ready Form IF-5 Charge Sheet</h3>
              <p className="feature-desc">
                Stage 9: Automatically populates standardized Form IF-5 charge sheets, complete with FIR particulars, accused profiles,
                chronology of events, evidence inventory, legal findings, and PDF export.
              </p>
              <div className="feature-tags">
                <span className="tag">Form IF-5 PDF</span>
                <span className="tag">Officer Revision History</span>
                <span className="tag">Review Workflow</span>
              </div>
            </div>

            {/* Feature 6 */}
            <div className="feature-card">
              <div className="feature-icon">🌐</div>
              <h3 className="feature-title">3D Crime Scene Reconstruction Entry</h3>
              <p className="feature-desc">
                Direct integration with the forensic 3D crime-scene reconstruction viewer to inspect physical trajectories,
                vehicle kinematics, impact dynamics, and spatial evidence layouts.
              </p>
              <div className="feature-tags">
                <span className="tag">Trajectory Viewer</span>
                <span className="tag">Scene Coordinates</span>
                <span className="tag">Spatial Verification</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Verification Banner */}
      <section className="landing-security-banner">
        <div className="landing-container">
          <div className="security-box">
            <div className="security-icon">🛡️</div>
            <div>
              <div className="security-title">Strict Evidentiary Integrity &amp; Zero Synthetic Fallback Policy</div>
              <div className="security-desc">
                Byomkesh AI never substitutes synthetic demonstration facts when extraction is incomplete or uncorroborated.
                Unsubstantiated legal ingredients are flagged for supervisory officer review rather than fabricated.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-container footer-content">
          <div className="footer-brand">
            <strong>BYOMKESH AI</strong> — Forensic Investigation Intelligence &amp; Statutory Charge-Sheet Platform
          </div>
          <div className="footer-links">
            <button className="footer-link-btn" onClick={onGoToLogin}>Officer Login</button>
            <span className="footer-sep">&bull;</span>
            <button className="footer-link-btn" onClick={onGoToWorkspace}>Cases Workspace</button>
          </div>
        </div>
      </footer>
    </div>
  );
}
