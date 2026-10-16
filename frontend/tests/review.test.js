/**
 * Frontend unit and integration tests for Charge-Sheet Human Review, Provenance, and Guarded Finalization.
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { reviewService } from "../src/services/reviewService.js";
import { artifactService } from "../src/services/artifactService.js";

function createMockResponse({
  status = 200,
  ok = true,
  json = null,
  text = "",
  headers = {},
  blob = null,
}) {
  const allHeaders = { "content-type": "application/json", ...headers };
  const headerMap = new Map(Object.entries(allHeaders));
  return {
    status,
    ok,
    headers: {
      get: (key) => headerMap.get(key.toLowerCase()) || headerMap.get(key) || null,
    },
    json: async () => json,
    text: async () => text,
    blob: async () => blob || new Blob([text || "fake-pdf"]),
  };
}

describe("Charge-Sheet Review & Finalization Service Suite", () => {
  const mockCaseId = "case-1234-abcd";

  it("1: getReviewData fetches review data from /api/v1/cases/{case_id}/review", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review`));
      assert.equal(options.method, "GET");
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          status: "review_required",
          data_version: 1,
          charge_sheet_data: {
            case_summary: { value: "Summary", origin: "extracted" },
          },
          completeness_report: {
            completeness_score: 0.85,
            critical_blockers: [],
            advisory_warnings: ["Pending verification of witness address"],
          },
          can_approve: true,
          can_finalize: false,
          is_finalized: false,
          draft_pdf_available: true,
          final_pdf_available: false,
        },
      });
    };

    const data = await reviewService.getReviewData(mockCaseId);
    assert.equal(data.status, "review_required");
    assert.equal(data.data_version, 1);
    assert.equal(data.completeness_report.critical_blockers.length, 0);
    assert.equal(data.can_approve, true);
    assert.equal(data.can_finalize, false);
  });

  it("2: applyCorrections sends corrections payload to /api/v1/cases/{case_id}/review/corrections", async () => {
    let capturedBody = null;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review/corrections`));
      assert.equal(options.method, "POST");
      capturedBody = JSON.parse(options.body);
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          status: "draft",
          data_version: 2,
          charge_sheet_data: {
            case_summary: {
              value: "Updated factual narrative",
              origin: "reviewer_corrected",
              corrected_by: "badge_104",
            },
          },
        },
      });
    };

    const res = await reviewService.applyCorrections(mockCaseId, {
      reviewer_id: "badge_104",
      reviewer_name: "Inspector Naik",
      comments: "Rectified timeline discrepancy",
      corrections: { case_summary: "Updated factual narrative" },
    });

    assert.equal(capturedBody.reviewer_id, "badge_104");
    assert.equal(capturedBody.corrections.case_summary, "Updated factual narrative");
    assert.equal(res.data_version, 2);
    assert.equal(res.charge_sheet_data.case_summary.origin, "reviewer_corrected");
  });

  it("3: addNote attaches observation note to audit trail", async () => {
    let capturedBody = null;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review/notes`));
      assert.equal(options.method, "POST");
      capturedBody = JSON.parse(options.body);
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          notes: [{ author_id: "adv_01", note_text: "Exhibits verified." }],
        },
      });
    };

    const res = await reviewService.addNote(mockCaseId, {
      author_id: "adv_01",
      note_text: "Exhibits verified.",
    });

    assert.equal(capturedBody.author_id, "adv_01");
    assert.equal(res.notes.length, 1);
  });

  it("4: recordDecision handles approve decision", async () => {
    let capturedBody = null;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review/decision`));
      assert.equal(options.method, "POST");
      capturedBody = JSON.parse(options.body);
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          status: "approved",
          can_finalize: true,
        },
      });
    };

    const res = await reviewService.recordDecision(mockCaseId, {
      decision: "approve",
      reviewer_id: "sp_01",
      comments: "Approved under Section 193 BNSS",
    });

    assert.equal(capturedBody.decision, "approve");
    assert.equal(res.status, "approved");
    assert.equal(res.can_finalize, true);
  });

  it("5: recordDecision handles finalize decision and final PDF generation", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review/decision`));
      const body = JSON.parse(options.body);
      assert.equal(body.decision, "finalize");
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          status: "finalized",
          is_finalized: true,
          final_pdf_available: true,
        },
      });
    };

    const res = await reviewService.recordDecision(mockCaseId, {
      decision: "finalize",
      reviewer_id: "sp_01",
    });

    assert.equal(res.status, "finalized");
    assert.equal(res.is_finalized, true);
    assert.equal(res.final_pdf_available, true);
  });

  it("6: getHistory retrieves revision and event audit trail", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes(`/api/v1/cases/${mockCaseId}/review/history`));
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: mockCaseId,
          current_version: 2,
          available_versions: [1, 2],
          events: [
            { event_type: "draft_created", version: 1 },
            { event_type: "correction_applied", version: 2 },
          ],
        },
      });
    };

    const hist = await reviewService.getHistory(mockCaseId);
    assert.equal(hist.current_version, 2);
    assert.equal(hist.events.length, 2);
  });

  it("7: artifactService supports final PDF URL and download endpoint", () => {
    const finalUrl = artifactService.getFinalPdfUrl(mockCaseId);
    assert.ok(finalUrl.includes(`/api/v1/cases/${mockCaseId}/artifacts/chargesheet_final.pdf`));
  });
});
