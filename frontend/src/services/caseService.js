/**
 * Case management and document upload service.
 */

import { apiClient } from "./apiClient.js";

export const caseService = {
  /**
   * List all known cases.
   * @returns {Promise<{ cases: Array, total: number }>}
   */
  async listCases() {
    return apiClient.get("/api/v1/cases");
  },

  /**
   * Retrieve detailed information for a specific case.
   * @param {string} caseId
   * @returns {Promise<Object>}
   */
  async getCase(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.get(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  },

  /**
   * Create a new investigation case.
   * @param {{ case_id?: string, title?: string, description?: string }} payload
   * @returns {Promise<{ case_id: string, status: string, created_at: string, storage_key: string }>}
   */
  async createCase(payload = {}) {
    return apiClient.post("/api/v1/cases", payload);
  },

  /**
   * Upload multiple evidence documents to a case workspace.
   * @param {string} caseId
   * @param {File[]} files
   * @returns {Promise<{ case_id: string, uploaded_count: number, failed_count: number, documents: Array }>}
   */
  async uploadDocuments(caseId, files) {
    if (!caseId) throw new Error("caseId is required");
    if (!files || files.length === 0) throw new Error("At least one file is required for upload");
    return apiClient.uploadFiles(`/api/v1/cases/${encodeURIComponent(caseId)}/documents`, files);
  },

  /**
   * Permanently delete a case workspace and all associated evidence.
   * @param {string} caseId
   * @returns {Promise<{ case_id: string, status: string, message: string }>}
   */
  async deleteCase(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.delete(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  },
};
