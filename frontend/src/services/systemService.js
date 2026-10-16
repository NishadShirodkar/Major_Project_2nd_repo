/**
 * Health and readiness probe service.
 */

import { apiClient } from "./apiClient.js";

export const systemService = {
  /**
   * Check backend server liveness.
   * @returns {Promise<{ status: string, service: string, version: string }>}
   */
  async getHealth() {
    return apiClient.get("/health");
  },

  /**
   * Check backend storage, legal references, and Gemini readiness.
   * @returns {Promise<{ status: string, ready: boolean, checks: Object, details: Object }>}
   */
  async getReadiness() {
    return apiClient.get("/ready");
  },
};
