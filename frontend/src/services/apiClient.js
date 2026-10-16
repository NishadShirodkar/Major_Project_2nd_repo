/**
 * Centralized API Client for Byomkesh AI.
 * Handles HTTP requests, error parsing, multipart file uploads, and network error handling.
 */

const API_BASE_URL = (
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class APIClientError extends Error {
  constructor(message, { status = 0, errorCode = "NETWORK_ERROR", detail = null, jobId = null, data = null } = {}) {
    super(message);
    this.name = "APIClientError";
    this.status = status;
    this.errorCode = errorCode;
    this.detail = detail;
    this.jobId = jobId;
    this.data = data;
  }
}

/**
 * Format human-readable error messages while guarding against leaking server internals.
 */
function parseErrorMessage(data, status) {
  if (!data) {
    if (status === 0) return "Unable to connect to Byomkesh AI backend. Please verify the server is running.";
    if (status === 404) return "The requested resource was not found on the server.";
    if (status === 413) return "Payload too large. File size exceeds permitted limit.";
    if (status === 415) return "Unsupported media type. Document format is not accepted.";
    if (status >= 500) return "An internal server error occurred. Please check backend logs.";
    return `Server returned HTTP status ${status}.`;
  }

  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  if (typeof data.message === "string") return data.message;
  if (typeof data.error === "string") return data.error;

  return `Request failed with HTTP ${status}.`;
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = { ...options.headers };

  try {
    const token = typeof localStorage !== "undefined" ? localStorage.getItem("byomkesh_token") : null;
    if (token && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } catch {
    // Ignore storage access error in restricted iframe/test contexts
  }

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new APIClientError(
      `Cannot connect to Byomkesh API server at ${API_BASE_URL}. Verify backend service is active.`,
      { status: 0, errorCode: "OFFLINE", detail: err.message }
    );
  }

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else if (!response.ok) {
    try {
      data = { detail: await response.text() };
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const message = parseErrorMessage(data, response.status);
    throw new APIClientError(message, {
      status: response.status,
      errorCode: data?.error_code || data?.error || `HTTP_${response.status}`,
      detail: data?.detail || null,
      jobId: data?.job_id || null,
      data: data,
    });
  }

  return data;
}

export const apiClient = {
  getBaseUrl() {
    return API_BASE_URL;
  },

  get(endpoint, options = {}) {
    return request(endpoint, { ...options, method: "GET" });
  },

  post(endpoint, body, options = {}) {
    return request(endpoint, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body || {}),
    });
  },

  delete(endpoint, options = {}) {
    return request(endpoint, { ...options, method: "DELETE" });
  },

  async uploadFiles(endpoint, files) {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    return request(endpoint, {
      method: "POST",
      body: formData,
    });
  },

  async downloadBlob(endpoint) {
    const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
    let response;
    try {
      response = await fetch(url, { method: "GET" });
    } catch (err) {
      throw new APIClientError(
        `Failed to reach server for download: ${err.message}`,
        { status: 0, errorCode: "OFFLINE" }
      );
    }

    if (!response.ok) {
      let detail = null;
      try {
        const json = await response.json();
        detail = json.detail || json.error;
      } catch {
        detail = await response.text();
      }
      throw new APIClientError(
        detail || `Download failed with HTTP ${response.status}`,
        { status: response.status, errorCode: `HTTP_${response.status}`, detail }
      );
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    let filename = "download.pdf";
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1];
    }
    return { blob, filename };
  },
};
