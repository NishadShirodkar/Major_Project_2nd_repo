import React, { useState } from "react";
import { authService } from "../services/authService.js";

export default function LoginPage({
  onLoginSuccess,
  onCancel,
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setErrorMessage("Please enter your officer username/badge and password.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await authService.login(username.trim(), password.trim());
      setIsLoading(false);
      if (res?.token && res?.officer) {
        onLoginSuccess(res.officer);
      }
    } catch (err) {
      setIsLoading(false);
      setErrorMessage(err.message || "Authentication failed. Please verify your credentials.");
    }
  };

  const fillQuickCredentials = (u, p) => {
    setUsername(u);
    setPassword(p);
    setErrorMessage(null);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Header Section */}
        <div className="login-header">
          <div className="login-badge-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
          </div>
          <h2 className="login-title">Officer Authentication</h2>
          <p className="login-subtitle">
            Secure sign-in for authorized police officers, forensic investigators, and supervisory personnel.
          </p>
        </div>

        {/* Security Alert Banner */}
        <div className="login-security-notice">
          <span className="notice-icon">🔒</span>
          <span>Official Law Enforcement System — Access is audited, monitored, and logged.</span>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div className="login-error-alert" id="login-error-msg">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group" style={{ marginBottom: "16px" }}>
            <label className="form-label" htmlFor="username-input">
              Officer Username or Badge ID
            </label>
            <input
              id="username-input"
              type="text"
              className="form-input"
              placeholder="e.g. inspector_sharma or DL-RN-4501"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: "22px" }}>
            <label className="form-label" htmlFor="password-input">
              Password
            </label>
            <input
              id="password-input"
              type="password"
              className="form-input"
              placeholder="Enter your security password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              autoComplete="current-password"
              required
            />
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ flex: 1, padding: "12px" }}
              disabled={isLoading}
              id="submit-login-btn"
            >
              {isLoading ? (
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                  <span className="status-dot pulsing"></span> Authenticating Officer...
                </span>
              ) : (
                "Authenticate & Sign In"
              )}
            </button>

            {onCancel && (
              <button
                type="button"
                className="btn btn-outline"
                onClick={onCancel}
                disabled={isLoading}
              >
                Cancel
              </button>
            )}
          </div>
        </form>

        {/* Quick Demo Credentials Assistant */}
        <div className="quick-creds-box">
          <div className="quick-creds-title">Configured Officer Directory (Click to Auto-fill)</div>
          <div className="quick-creds-grid">
            <button
              type="button"
              className="quick-cred-btn"
              onClick={() => fillQuickCredentials("inspector_sharma", "investigator123")}
              title="Inspector Ramesh Sharma, SHO Rajinder Nagar PS"
            >
              <div className="cred-role">SHO (Rajinder Nagar PS)</div>
              <div className="cred-user">inspector_sharma</div>
            </button>

            <button
              type="button"
              className="quick-cred-btn"
              onClick={() => fillQuickCredentials("officer_rao", "delhipolice2026")}
              title="Sub-Inspector K. V. Rao, Investigating Officer"
            >
              <div className="cred-role">Investigating Officer (IO)</div>
              <div className="cred-user">officer_rao</div>
            </button>

            <button
              type="button"
              className="quick-cred-btn"
              onClick={() => fillQuickCredentials("dsp_byomkesh", "byomkeshai2026")}
              title="DSP Byomkesh Bakshi, Forensic Intelligence Director"
            >
              <div className="cred-role">Forensic Director</div>
              <div className="cred-user">dsp_byomkesh</div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
