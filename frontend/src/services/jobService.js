/**
 * Workflow processing and job monitoring service.
 */

import { apiClient } from "./apiClient.js";

export const PIPELINE_STAGES = [
  { id: "document_intake", name: "1. Document Intake", description: "Storage isolation and file inventory" },
  { id: "ocr", name: "2. OCR & Vision Extraction", description: "Multi-page text extraction" },
  { id: "document_parsing", name: "3. Document Parsing", description: "Structured JSON entity extraction" },
  { id: "investigation_knowledge_graph", name: "4. Knowledge Graph", description: "Entity resolution and timeline synthesis" },
  { id: "canonical_investigation", name: "5. Canonical Model", description: "Unified investigation state assembly" },
  { id: "evidence_validation", name: "6. Evidence Validation", description: "Mandatory rule and contradiction checks" },
  { id: "case_context", name: "7. Case Context", description: "Context bundling for legal engine" },
  { id: "legal_reasoning", name: "8. Legal Reasoning", description: "BNS statutory elements & charge analysis" },
  { id: "chargesheet_population", name: "9. Charge-Sheet Drafting", description: "Draft charge-sheet PDF & data compilation" },
];

export const jobService = {
  /**
   * Start 9-stage pipeline execution for a case.
   * @param {string} caseId
   * @param {{ resume?: boolean, mock_llm?: boolean }} options
   * @returns {Promise<{ job_id: string, case_id: string, status: string, message: string }>}
   */
  async startProcessing(caseId, options = {}) {
    if (!caseId) throw new Error("caseId is required");
    try {
      return await apiClient.post(`/api/v1/cases/${encodeURIComponent(caseId)}/process`, {
        resume: Boolean(options.resume),
        mock_llm: Boolean(options.mock_llm),
      });
    } catch (err) {
      if (err.status === 409) {
        const regexMatch = (err.message || "").match(/job '([a-f0-9-]+)'/i);
        const activeJobId = err.jobId || err.data?.job_id || (regexMatch ? regexMatch[1] : null);
        if (activeJobId) {
          return {
            job_id: activeJobId,
            case_id: caseId,
            status: "running",
            message: `Reconnected to actively running pipeline job '${activeJobId}'.`,
          };
        }
      }
      throw err;
    }
  },

  /**
   * Retrieve current job execution status.
   * @param {string} jobId
   * @returns {Promise<Object>}
   */
  async getJob(jobId) {
    if (!jobId) throw new Error("jobId is required");
    return apiClient.get(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
  },

  /**
   * Force reset any active/hung processing lock on a case.
   * @param {string} caseId
   */
  async resetProcessing(caseId) {
    if (!caseId) throw new Error("caseId is required");
    return apiClient.post(`/api/v1/cases/${encodeURIComponent(caseId)}/reset-processing`, {});
  },
};
