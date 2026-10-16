import React from "react";

export default function Header({
  activeView,
  onViewChange,
  healthStatus,
  onRefresh,
  isRefreshing,
  currentOfficer,
  onLogout,
}) {
  return (
    <header className="app-header">
      <div
        className="brand-section"
        style={{ cursor: "pointer" }}
        onClick={() => onViewChange("landing")}
        title="Byomkesh AI Platform"
      >
        <div className="brand-logo">BYOMKESH AI</div>
        <div>
          <div className="brand-title">Forensic Investigation Intelligence Platform</div>
          <div className="brand-tagline">AI-Assisted Investigation &amp; Statutory Charge-Sheet System</div>
        </div>
      </div>

      <nav className="nav-tabs">
        <button
          className={`nav-tab-btn ${activeView === "landing" ? "active" : ""}`}
          onClick={() => onViewChange("landing")}
          id="nav-landing-btn"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
            <polyline points="9 22 9 12 15 12 15 22"></polyline>
          </svg>
          Home / Overview
        </button>

        <button
          className={`nav-tab-btn ${activeView === "workspace" ? "active" : ""}`}
          onClick={() => onViewChange("workspace")}
          id="nav-workspace-btn"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
          Investigation Cases
        </button>

        <button
          className={`nav-tab-btn ${activeView === "simulation" ? "active" : ""}`}
          onClick={() => onViewChange("simulation")}
          id="nav-3d-btn"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
          </svg>
          3D Scene Simulation
        </button>
      </nav>

      <div className="header-status">
        {/* Officer Profile Badge */}
        {currentOfficer && (
          <div
            className="header-officer-badge"
            title={`${currentOfficer.rank} — ${currentOfficer.police_station}`}
          >
            <span className="officer-icon">👮</span>
            <div className="officer-meta">
              <div className="officer-name">{currentOfficer.name}</div>
              <div className="officer-badge-id">{currentOfficer.badge_number}</div>
            </div>
            {onLogout && (
              <button
                className="btn-logout"
                onClick={onLogout}
                title="Sign out of Byomkesh session"
                id="header-logout-btn"
              >
                Sign Out
              </button>
            )}
          </div>
        )}

        {healthStatus?.online ? (
          <span className="status-badge status-online" title={healthStatus?.details || "Backend connected"}>
            <span className="status-dot"></span>
            FASTAPI ONLINE
          </span>
        ) : (
          <span className="status-badge status-offline" title="Backend unreachable at http://127.0.0.1:8000">
            <span className="status-dot"></span>
            BACKEND OFFLINE
          </span>
        )}

        <button
          className="btn btn-outline btn-sm"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh case data and server status"
          id="header-refresh-btn"
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{ animation: isRefreshing ? "spin 1s linear infinite" : "none" }}
          >
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
          </svg>
          {isRefreshing ? "Checking..." : "Refresh"}
        </button>
      </div>
    </header>
  );
}
