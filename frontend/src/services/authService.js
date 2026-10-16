/**
 * Authentication and session service for Byomkesh AI.
 * Handles investigator sign-in, token storage, session validation, and sign-out.
 */

import { apiClient } from "./apiClient.js";

const TOKEN_KEY = "byomkesh_token";
const OFFICER_KEY = "byomkesh_officer";

export const authService = {
  getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },

  getCurrentOfficer() {
    try {
      const data = localStorage.getItem(OFFICER_KEY);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated() {
    return Boolean(this.getToken());
  },

  async login(username, password) {
    const res = await apiClient.post("/api/v1/auth/login", {
      username: username.trim(),
      password: password.trim(),
    });

    if (res?.token) {
      try {
        localStorage.setItem(TOKEN_KEY, res.token);
        localStorage.setItem(OFFICER_KEY, JSON.stringify(res.officer));
      } catch (err) {
        console.warn("Unable to persist auth token to localStorage:", err);
      }
    }

    return res;
  },

  async validateSession() {
    const token = this.getToken();
    if (!token) return { valid: false, officer: null };

    try {
      const res = await apiClient.get("/api/v1/auth/me");
      if (res?.valid && res.officer) {
        localStorage.setItem(OFFICER_KEY, JSON.stringify(res.officer));
        return { valid: true, officer: res.officer };
      }
      this.logout();
      return { valid: false, officer: null };
    } catch {
      this.logout();
      return { valid: false, officer: null };
    }
  },

  async logout() {
    const token = this.getToken();
    try {
      if (token) {
        await apiClient.post("/api/v1/auth/logout");
      }
    } catch {
      // Ignore network errors on logout
    } finally {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(OFFICER_KEY);
      } catch {
        // Ignore storage errors
      }
    }
  },
};
