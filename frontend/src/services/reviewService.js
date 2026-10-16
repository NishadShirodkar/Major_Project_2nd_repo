/**
 * Charge-sheet human review, field correction, notes, and finalization service.
 */

import { apiClient } from "./apiClient.js";

export const reviewService = {
  /**
   * Get charge-sheet review data, completeness report, and review state.
   * @param {string} caseId
   * @returns {Promise<Object>}
   */
  async getReviewData(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.get(`/api/v1/cases/${encodeURIComponent(caseId)}/review`);
  },

  /**
   * Apply field corrections to the charge sheet, creating a new version.
   * @param {string} caseId
   * @param {Object} payload { reviewer_id, reviewer_name, comments, corrections: { [field]: value } }
   * @returns {Promise<Object>}
   */
  async applyCorrections(caseId, payload) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.post(`/api/v1/cases/${encodeURIComponent(caseId)}/review/corrections`, payload);
  },

  /**
   * Add a review observation note.
   * @param {string} caseId
   * @param {Object} payload { author_id, author_name, note_text }
   * @returns {Promise<Object>}
   */
  async addNote(caseId, payload) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.post(`/api/v1/cases/${encodeURIComponent(caseId)}/review/notes`, payload);
  },

  /**
   * Record a review decision (approve, reject, request_revision, finalize).
   * @param {string} caseId
   * @param {Object} payload { decision, reviewer_id, reviewer_name, comments, rejection_reason }
   * @returns {Promise<Object>}
   */
  async recordDecision(caseId, payload) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.post(`/api/v1/cases/${encodeURIComponent(caseId)}/review/decision`, payload);
  },

  /**
   * Retrieve chronological revision and event history.
   * @param {string} caseId
   * @returns {Promise<Object>}
   */
  async getHistory(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.get(`/api/v1/cases/${encodeURIComponent(caseId)}/review/history`);
  },

  /**
   * Query case-isolated RAG retrieval index for matching passages.
   * @param {string} caseId
   * @param {string} query
   * @param {number} topK
   * @returns {Promise<Object>}
   */
  async searchEvidence(caseId, query, topK = 5) {
    if (!caseId) throw new Error("caseId is required");
    if (!query) throw new Error("query is required");
    return apiClient.get(`/api/v1/cases/${encodeURIComponent(caseId)}/review/retrieval?query=${encodeURIComponent(query)}&top_k=${topK}`);
  },
};

