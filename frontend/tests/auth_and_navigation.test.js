/**
 * Byomkesh AI — Authentication & End-to-End Navigation Test Suite
 * Tests investigator authentication, session persistence, automatic Bearer token injection,
 * and the continuous workflow navigation contracts.
 */

import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { apiClient } from "../src/services/apiClient.js";
import { authService } from "../src/services/authService.js";

// Mock localStorage for node environment
class MockLocalStorage {
  constructor() {
    this.store = new Map();
  }
  getItem(key) {
    return this.store.get(key) || null;
  }
  setItem(key, val) {
    this.store.set(key, String(val));
  }
  removeItem(key) {
    this.store.delete(key);
  }
  clear() {
    this.store.clear();
  }
}

function createMockResponse({
  status = 200,
  ok = true,
  json = null,
  text = "",
  headers = { "content-type": "application/json" },
}) {
  const headerMap = new Map(Object.entries(headers));
  return {
    status,
    ok,
    headers: {
      get: (key) => headerMap.get(key.toLowerCase()) || headerMap.get(key) || null,
    },
    json: async () => json,
    text: async () => text,
  };
}

describe("Authentication & Navigation Service Suite", () => {
  let originalFetch;
  let originalLocalStorage;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalLocalStorage = globalThis.localStorage;
    globalThis.localStorage = new MockLocalStorage();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalLocalStorage;
  });

  it("1: Initial state is unauthenticated", () => {
    assert.equal(authService.isAuthenticated(), false);
    assert.equal(authService.getToken(), null);
    assert.equal(authService.getCurrentOfficer(), null);
  });

  it("2: login authenticates with backend and stores session token", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/api/v1/auth/login"));
      assert.equal(options.method, "POST");
      const body = JSON.parse(options.body);
      assert.equal(body.username, "inspector_sharma");
      assert.equal(body.password, "investigator123");

      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          token: "session_token_xyz_123",
          token_type: "Bearer",
          expires_in_seconds: 86400,
          officer: {
            officer_id: "dl_rn_4501",
            name: "Inspector Ramesh Sharma",
            rank: "Station House Officer (SHO)",
            police_station: "Rajinder Nagar Police Station, Delhi",
            badge_number: "DL-RN-4501",
            role: "sho",
          },
        },
      });
    };

    const res = await authService.login("inspector_sharma", "investigator123");
    assert.equal(res.token, "session_token_xyz_123");
    assert.equal(authService.isAuthenticated(), true);
    assert.equal(authService.getToken(), "session_token_xyz_123");
    assert.equal(authService.getCurrentOfficer()?.badge_number, "DL-RN-4501");
  });

  it("3: apiClient automatically injects Authorization header when authenticated", async () => {
    globalThis.localStorage.setItem("byomkesh_token", "bearer_token_abc");

    globalThis.fetch = async (url, options) => {
      assert.equal(options.headers["Authorization"], "Bearer bearer_token_abc");
      return createMockResponse({
        status: 200,
        ok: true,
        json: { status: "ok" },
      });
    };

    const res = await apiClient.get("/api/v1/cases");
    assert.deepEqual(res, { status: "ok" });
  });

  it("4: validateSession validates active token via /api/v1/auth/me", async () => {
    globalThis.localStorage.setItem("byomkesh_token", "valid_token_789");

    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/api/v1/auth/me"));
      assert.equal(options.headers["Authorization"], "Bearer valid_token_789");
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          valid: true,
          officer: {
            officer_id: "dl_cid_001",
            name: "DSP Byomkesh Bakshi",
            badge_number: "DL-CID-001",
          },
        },
      });
    };

    const status = await authService.validateSession();
    assert.equal(status.valid, true);
    assert.equal(status.officer?.name, "DSP Byomkesh Bakshi");
  });

  it("5: logout revokes session and clears storage", async () => {
    globalThis.localStorage.setItem("byomkesh_token", "token_to_purge");
    globalThis.localStorage.setItem("byomkesh_officer", JSON.stringify({ name: "Officer" }));

    let logoutCalled = false;
    globalThis.fetch = async (url, options) => {
      if (url.includes("/api/v1/auth/logout")) {
        logoutCalled = true;
        assert.equal(options.method, "POST");
        assert.equal(options.headers["Authorization"], "Bearer token_to_purge");
        return createMockResponse({
          status: 200,
          ok: true,
          json: { status: "logged_out" },
        });
      }
      return createMockResponse({ status: 404, ok: false });
    };

    await authService.logout();
    assert.equal(logoutCalled, true);
    assert.equal(authService.isAuthenticated(), false);
    assert.equal(authService.getToken(), null);
    assert.equal(authService.getCurrentOfficer(), null);
  });
});
