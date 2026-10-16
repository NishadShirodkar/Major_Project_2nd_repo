import React from "react";

export function LoadingState({ message = "Loading data from Byomkesh backend..." }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        color: "var(--text-secondary)",
      }}
    >
      <div
        style={{
          width: "36px",
          height: "36px",
          border: "3px solid var(--border-subtle)",
          borderTopColor: "var(--color-accent)",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
          marginBottom: "16px",
        }}
      />
      <div style={{ fontSize: "14px", fontWeight: "500" }}>{message}</div>
    </div>
  );
}

export function ErrorState({ title = "Operation Failed", message, onRetry }) {
  return (
    <div
      className="card"
      style={{
        borderColor: "var(--color-danger-border)",
        background: "rgba(239, 68, 68, 0.05)",
        padding: "24px",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: "14px" }}>
        <div
          style={{
            color: "var(--color-danger)",
            background: "var(--color-danger-bg)",
            padding: "8px",
            borderRadius: "50%",
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <h4 style={{ margin: "0 0 6px 0", color: "var(--color-danger)", fontSize: "15px" }}>
            {title}
          </h4>
          <p style={{ margin: "0 0 14px 0", color: "var(--text-secondary)", fontSize: "13px" }}>
            {message}
          </p>
          {onRetry && (
            <button className="btn btn-secondary btn-sm" onClick={onRetry}>
              Retry Request
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title = "No Items Found", message, action }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "48px 24px",
        background: "var(--bg-surface)",
        border: "1px dashed var(--border-strong)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <div style={{ color: "var(--text-muted)", marginBottom: "12px" }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
      </div>
      <h3 style={{ margin: "0 0 6px 0", fontSize: "16px", color: "var(--text-primary)" }}>{title}</h3>
      <p style={{ margin: "0 0 20px 0", fontSize: "13px", color: "var(--text-secondary)", maxWidth: "480px", marginInline: "auto" }}>
        {message}
      </p>
      {action}
    </div>
  );
}
