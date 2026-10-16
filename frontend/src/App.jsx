import React, { Component, Suspense, useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import InvestigationPage from "./pages/InvestigationPage.jsx";
import SceneViewer from "./simulation/SceneViewer.jsx";
import { systemService } from "./services/systemService.js";
import { authService } from "./services/authService.js";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Byomkesh AI ErrorBoundary caught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            width: "100vw",
            height: "100vh",
            background: "var(--bg-base)",
            color: "var(--color-danger)",
            padding: "32px",
            fontFamily: "var(--font-mono)",
            boxSizing: "border-box",
            overflow: "auto",
          }}
        >
          <div style={{ maxWidth: "800px", margin: "40px auto" }}>
            <h2
              style={{
                color: "var(--color-accent)",
                borderBottom: "1px solid var(--border-subtle)",
                paddingBottom: "12px",
                letterSpacing: "1px",
              }}
            >
              ⚠ BYOMKESH PLATFORM RUNTIME ERROR
            </h2>
            <p style={{ color: "var(--color-warning)", fontSize: "16px", margin: "16px 0" }}>
              {this.state.error?.message || "An unexpected error occurred during execution."}
            </p>
            <pre
              style={{
                background: "#040810",
                padding: "16px",
                border: "1px solid var(--border-subtle)",
                borderRadius: "4px",
                color: "var(--text-secondary)",
                fontSize: "12px",
                whiteSpace: "pre-wrap",
                lineHeight: "1.5",
              }}
            >
              {this.state.error?.stack}
            </pre>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="btn btn-primary"
              style={{ marginTop: "20px" }}
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  // Navigation State: 'landing' | 'login' | 'workspace' | 'simulation'
  const [activeView, setActiveView] = useState("landing");
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [currentOfficer, setCurrentOfficer] = useState(null);
  const [healthStatus, setHealthStatus] = useState({ online: false, details: "Checking backend..." });
  const [refreshSignal, setRefreshSignal] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Initialize Auth & Synchronize with URL hash on mount
  useEffect(() => {
    const officer = authService.getCurrentOfficer();
    if (officer) {
      setCurrentOfficer(officer);
    }

    // Hash router handler
    const parseHash = () => {
      const hash = window.location.hash.replace(/^#\/?/, "");
      if (!hash || hash === "landing") {
        setActiveView("landing");
        setSelectedCaseId(null);
      } else if (hash === "login") {
        setActiveView("login");
      } else if (hash === "cases" || hash === "dashboard") {
        setActiveView("workspace");
        setSelectedCaseId(null);
      } else if (hash.startsWith("case/")) {
        const cId = hash.replace("case/", "");
        setActiveView("workspace");
        setSelectedCaseId(cId);
      } else if (hash.startsWith("simulation/")) {
        const cId = hash.replace("simulation/", "");
        setActiveView("simulation");
        setSelectedCaseId(cId || null);
      } else if (hash === "simulation") {
        setActiveView("simulation");
      }
    };

    parseHash();
    window.addEventListener("hashchange", parseHash);
    return () => window.removeEventListener("hashchange", parseHash);
  }, []);

  // Sync state to URL hash
  const navigateTo = (view, caseId = null) => {
    setActiveView(view);
    setSelectedCaseId(caseId);

    if (view === "landing") {
      window.location.hash = "#landing";
    } else if (view === "login") {
      window.location.hash = "#login";
    } else if (view === "workspace") {
      if (caseId) {
        window.location.hash = `#case/${caseId}`;
      } else {
        window.location.hash = "#cases";
      }
    } else if (view === "simulation") {
      if (caseId) {
        window.location.hash = `#simulation/${caseId}`;
      } else {
        window.location.hash = "#simulation";
      }
    }
  };

  // Probe backend health and readiness
  const checkHealth = async () => {
    setIsRefreshing(true);
    try {
      const [health, ready] = await Promise.allSettled([
        systemService.getHealth(),
        systemService.getReadiness(),
      ]);

      const isOnline = health.status === "fulfilled" && health.value?.status === "ok";
      const readyDetails = ready.status === "fulfilled" ? ready.value?.status : "offline";

      setHealthStatus({
        online: isOnline,
        details: isOnline ? `FastAPI ${health.value.version} (Ready: ${readyDetails})` : "Backend offline",
      });
      setIsRefreshing(false);
    } catch {
      setHealthStatus({ online: false, details: "Backend unreachable" });
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkHealth();
    // Heartbeat every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleManualRefresh = () => {
    checkHealth();
    setRefreshSignal((prev) => prev + 1);
  };

  const handleLoginSuccess = (officer) => {
    setCurrentOfficer(officer);
    navigateTo("workspace");
  };

  const handleLogout = async () => {
    await authService.logout();
    setCurrentOfficer(null);
    navigateTo("landing");
  };

  return (
    <ErrorBoundary>
      <div className="app-container">
        {/* Render Global Header in all views except simulation */}
        {activeView !== "simulation" && (
          <Header
            activeView={activeView}
            onViewChange={(v) => navigateTo(v, selectedCaseId)}
            healthStatus={healthStatus}
            onRefresh={handleManualRefresh}
            isRefreshing={isRefreshing}
            currentOfficer={currentOfficer}
            onLogout={handleLogout}
          />
        )}

        {/* View Switcher */}
        {activeView === "landing" ? (
          <LandingPage
            onGoToLogin={() => navigateTo("login")}
            onGoToWorkspace={() => navigateTo("workspace")}
            isAuthenticated={Boolean(currentOfficer)}
            currentOfficer={currentOfficer}
          />
        ) : activeView === "login" ? (
          <LoginPage
            onLoginSuccess={handleLoginSuccess}
            onCancel={() => navigateTo("landing")}
          />
        ) : activeView === "simulation" ? (
          <Suspense
            fallback={
              <div
                style={{
                  width: "100vw",
                  height: "100vh",
                  background: "#05080f",
                  color: "#00f0ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "'Courier New', Courier, monospace",
                  fontSize: "16px",
                  letterSpacing: "3px",
                }}
              >
                [ INITIALIZING 3D CRIME SCENE SIMULATION ENGINE... ]
              </div>
            }
          >
            <SceneViewer
              initialCaseId={selectedCaseId}
              onReturnToWorkspace={() => navigateTo("workspace", selectedCaseId)}
            />
          </Suspense>
        ) : (
          <main className="main-content">
            {selectedCaseId ? (
              <InvestigationPage
                caseId={selectedCaseId}
                onBackToDashboard={() => navigateTo("workspace", null)}
                onLaunchSimulation={() => navigateTo("simulation", selectedCaseId)}
              />
            ) : (
              <DashboardPage
                onSelectCase={(id) => navigateTo("workspace", id)}
                onLaunchSimulation={() => navigateTo("simulation", null)}
                refreshSignal={refreshSignal}
              />
            )}
          </main>
        )}
      </div>
    </ErrorBoundary>
  );
}