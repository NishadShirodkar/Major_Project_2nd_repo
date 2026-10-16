/**
 * Case artifact discovery, inspection, and PDF download service.
 */

import { apiClient } from "./apiClient.js";

export const artifactService = {
  /**
   * List all generated case artifacts.
   * @param {string} caseId
   * @returns {Promise<{ case_id: string, artifacts: Array, draft_pdf_available: boolean }>}
   */
  async listArtifacts(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.get(`/api/v1/cases/${encodeURIComponent(caseId)}/artifacts`);
  },

  /**
   * Retrieve the parsed JSON content of a specific artifact.
   * @param {string} caseId
   * @param {string} artifactName
   * @returns {Promise<Object>}
   */
  async getArtifactContent(caseId, artifactName) {
    if (!caseId || !artifactName) throw new Error("caseId and artifactName are required");
    return apiClient.get(
      `/api/v1/cases/${encodeURIComponent(caseId)}/artifacts/content/${encodeURIComponent(artifactName)}`
    );
  },

  /**
   * Get direct URL to the draft PDF (for embedding or direct links).
   * @param {string} caseId
   * @returns {string}
   */
  getDraftPdfUrl(caseId) {
    return `${apiClient.getBaseUrl()}/api/v1/cases/${encodeURIComponent(caseId)}/artifacts/chargesheet.pdf`;
  },

  /**
   * Download the draft charge-sheet PDF file.
   * @param {string} caseId
   */
  async downloadDraftPdf(caseId) {
    if (!caseId) throw new Error("caseId is required");
    const endpoint = `/api/v1/cases/${encodeURIComponent(caseId)}/artifacts/chargesheet.pdf`;
    const { blob, filename } = await apiClient.downloadBlob(endpoint);

    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename || `draft_chargesheet_${caseId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 1000);
  },

  /**
   * Get direct URL to the finalized PDF.
   * @param {string} caseId
   * @returns {string}
   */
  getFinalPdfUrl(caseId) {
    return `${apiClient.getBaseUrl()}/api/v1/cases/${encodeURIComponent(caseId)}/artifacts/chargesheet_final.pdf`;
  },

  /**
   * Download the officially finalized charge-sheet PDF file.
   * @param {string} caseId
   */
  async downloadFinalPdf(caseId) {
    if (!caseId) throw new Error("caseId is required");
    const endpoint = `/api/v1/cases/${encodeURIComponent(caseId)}/artifacts/chargesheet_final.pdf`;
    const { blob, filename } = await apiClient.downloadBlob(endpoint);

    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename || `final_chargesheet_${caseId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 1000);
  },
};

