/**
 * Byomkesh AI — Frontend Integration & Service Unit Test Suite
 * Validates API client error handling, case management, multipart document upload,
 * job monitoring and polling lifecycle, artifact discovery, and draft PDF downloads.
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { apiClient, APIClientError } from "../src/services/apiClient.js";
import { caseService } from "../src/services/caseService.js";
import { jobService, PIPELINE_STAGES } from "../src/services/jobService.js";
import { artifactService } from "../src/services/artifactService.js";
import { systemService } from "../src/services/systemService.js";

// Helper mock response generator
function createMockResponse({
  status = 200,
  ok = true,
  json = null,
  text = "",
  headers = {},
  blob = null,
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
    blob: async () => blob || new Blob([text || "fake-content"]),
  };
}

describe("Byomkesh AI Frontend Integration Suite", () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  // 1. Application builds successfully (verified via build script)
  it("Requirement 1: Build script and services initialize properly", () => {
    assert.equal(typeof apiClient.get, "function");
    assert.equal(typeof caseService.listCases, "function");
    assert.equal(typeof jobService.startProcessing, "function");
    assert.equal(typeof artifactService.downloadDraftPdf, "function");
  });

  // 2. API client handles successful responses
  it("Requirement 2: API client handles successful JSON responses", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/health"));
      assert.equal(options.method, "GET");
      return createMockResponse({
        status: 200,
        ok: true,
        json: { status: "ok", service: "byomkesh-ai", version: "1.0.0" },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await systemService.getHealth();
    assert.equal(res.status, "ok");
    assert.equal(res.service, "byomkesh-ai");
  });

  // 3. API client handles server errors and network failures
  it("Requirement 3: API client handles 404, 500, and offline network errors cleanly", async () => {
    // 3a. 404 Not Found
    globalThis.fetch = async () => {
      return createMockResponse({
        status: 404,
        ok: false,
        json: { detail: "Case 'missing-case' not found", error_code: "CASE_NOT_FOUND" },
        headers: { "content-type": "application/json" },
      });
    };

    await assert.rejects(
      async () => await caseService.getCase("missing-case"),
      (err) => {
        assert.ok(err instanceof APIClientError);
        assert.equal(err.status, 404);
        assert.equal(err.errorCode, "CASE_NOT_FOUND");
        assert.equal(err.message, "Case 'missing-case' not found");
        return true;
      }
    );

    // 3b. Network offline / connection refused
    globalThis.fetch = async () => {
      throw new Error("Failed to fetch: Connection refused");
    };

    await assert.rejects(
      async () => await systemService.getHealth(),
      (err) => {
        assert.ok(err instanceof APIClientError);
        assert.equal(err.status, 0);
        assert.equal(err.errorCode, "OFFLINE");
        assert.ok(err.message.includes("Cannot connect to Byomkesh API server"));
        return true;
      }
    );
  });

  // 4. Case list loads from API
  it("Requirement 4: Case list loads from GET /api/v1/cases", async () => {
    globalThis.fetch = async (url) => {
      assert.ok(url.endsWith("/api/v1/cases"));
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          cases: [
            {
              case_id: "test-case-001",
              created_at: "2026-10-15T18:00:00Z",
              document_count: 3,
              status: "processed",
              validation_disposition: "draft_allowed",
              review_status: "review_required",
            },
          ],
          total: 1,
        },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await caseService.listCases();
    assert.equal(res.total, 1);
    assert.equal(res.cases[0].case_id, "test-case-001");
    assert.equal(res.cases[0].validation_disposition, "draft_allowed");
  });

  // 5. Case creation invokes the correct endpoint
  it("Requirement 5: Case creation invokes POST /api/v1/cases with payload", async () => {
    let capturedBody;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.endsWith("/api/v1/cases"));
      assert.equal(options.method, "POST");
      capturedBody = JSON.parse(options.body);
      return createMockResponse({
        status: 201,
        ok: true,
        json: {
          case_id: "demo-2026-99",
          status: "created",
          created_at: "2026-10-15T18:01:00Z",
          storage_key: "CASE_abc123",
        },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await caseService.createCase({
      case_id: "demo-2026-99",
      title: "Market Road Collision",
      description: "Preliminary FIR filed",
    });

    assert.equal(res.case_id, "demo-2026-99");
    assert.equal(capturedBody.case_id, "demo-2026-99");
    assert.equal(capturedBody.title, "Market Road Collision");
  });

  // 6. Case selection loads the correct details
  it("Requirement 6: Case selection loads details from GET /api/v1/cases/{case_id}", async () => {
    globalThis.fetch = async (url) => {
      assert.ok(url.includes("/api/v1/cases/case-detail-01"));
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          case_id: "case-detail-01",
          created_at: "2026-10-15T18:00:00Z",
          title: "Investigation 01",
          status: "documents_uploaded",
          document_count: 2,
          documents: [
            {
              document_id: "doc-1",
              original_filename: "FIR.pdf",
              stored_filename: "doc-1_FIR.pdf",
              size_bytes: 4096,
              media_type: "application/pdf",
              uploaded_at: "2026-10-15T18:05:00Z",
            },
          ],
        },
        headers: { "content-type": "application/json" },
      });
    };

    const details = await caseService.getCase("case-detail-01");
    assert.equal(details.case_id, "case-detail-01");
    assert.equal(details.document_count, 2);
    assert.equal(details.documents[0].original_filename, "FIR.pdf");
  });

  // 7. Multiple document uploads use the correct multipart field
  it("Requirement 7: Document upload sends FormData with 'files' field name", async () => {
    let capturedFormData;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/api/v1/cases/test-case/documents"));
      assert.equal(options.method, "POST");
      assert.ok(options.body instanceof FormData);
      capturedFormData = options.body;
      return createMockResponse({
        status: 201,
        ok: true,
        json: {
          case_id: "test-case",
          uploaded_count: 2,
          failed_count: 0,
          documents: [
            { document_id: "d1", original_filename: "FIR.pdf", size_bytes: 100, media_type: "application/pdf", status: "uploaded", errors: [] },
            { document_id: "d2", original_filename: "statement.pdf", size_bytes: 200, media_type: "application/pdf", status: "uploaded", errors: [] },
          ],
        },
        headers: { "content-type": "application/json" },
      });
    };

    const dummyFile1 = new File(["dummy1"], "FIR.pdf", { type: "application/pdf" });
    const dummyFile2 = new File(["dummy2"], "statement.pdf", { type: "application/pdf" });

    const uploadRes = await caseService.uploadDocuments("test-case", [dummyFile1, dummyFile2]);
    assert.equal(uploadRes.uploaded_count, 2);
    assert.equal(capturedFormData.getAll("files").length, 2);
  });

  // 8. Upload failures are displayed accurately
  it("Requirement 8: Upload errors (e.g. 415 Unsupported Media) throw formatted APIClientError", async () => {
    globalThis.fetch = async () => {
      return createMockResponse({
        status: 415,
        ok: false,
        json: {
          error: "UNSUPPORTED_MEDIA_TYPE",
          detail: "Document 'malicious.exe' with extension '.exe' is not supported.",
          error_code: "UNSUPPORTED_MEDIA_TYPE",
        },
        headers: { "content-type": "application/json" },
      });
    };

    const dummyFile = new File(["exe"], "malicious.exe", { type: "application/x-msdownload" });
    await assert.rejects(
      async () => await caseService.uploadDocuments("case-1", [dummyFile]),
      (err) => {
        assert.ok(err instanceof APIClientError);
        assert.equal(err.status, 415);
        assert.ok(err.message.includes(".exe' is not supported"));
        return true;
      }
    );
  });

  // 9. Processing creates a job and displays its actual status
  it("Requirement 9: Processing triggers POST /api/v1/cases/{case_id}/process and returns job_id", async () => {
    let capturedBody;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/api/v1/cases/case-proc-1/process"));
      assert.equal(options.method, "POST");
      capturedBody = JSON.parse(options.body);
      return createMockResponse({
        status: 202,
        ok: true,
        json: {
          job_id: "job-uuid-1234",
          case_id: "case-proc-1",
          status: "queued",
          message: "Case processing workflow queued successfully.",
        },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await jobService.startProcessing("case-proc-1", { mock_llm: true, resume: false });
    assert.equal(res.job_id, "job-uuid-1234");
    assert.equal(res.status, "queued");
    assert.equal(capturedBody.mock_llm, true);
    assert.equal(capturedBody.resume, false);
  });

  // 10. Polling returns status and reads completed stages
  it("Requirement 10: Polling retrieves job status with truthful completed_stages", async () => {
    globalThis.fetch = async (url) => {
      assert.ok(url.includes("/api/v1/jobs/job-uuid-1234"));
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          job_id: "job-uuid-1234",
          case_id: "case-proc-1",
          status: "completed",
          completed_stages: [
            "document_intake",
            "ocr",
            "document_parsing",
            "investigation_knowledge_graph",
            "canonical_investigation",
            "evidence_validation",
            "case_context",
            "legal_reasoning",
            "chargesheet_population",
          ],
          stage_records: PIPELINE_STAGES.map((s) => ({
            stage_name: s.id,
            status: "completed",
            error_message: null,
          })),
          validation_disposition: "draft_allowed",
          artifacts_available: ["processed/chargesheet/draft/ChargeSheet_v1_review.pdf"],
        },
        headers: { "content-type": "application/json" },
      });
    };

    const job = await jobService.getJob("job-uuid-1234");
    assert.equal(job.status, "completed");
    assert.equal(job.completed_stages.length, 9);
    assert.equal(job.validation_disposition, "draft_allowed");
  });

  // 11. 9-stage pipeline integrity
  it("Requirement 11: All 9 pipeline stages are defined in canonical sequence", () => {
    assert.equal(PIPELINE_STAGES.length, 9);
    assert.equal(PIPELINE_STAGES[0].id, "document_intake");
    assert.equal(PIPELINE_STAGES[1].id, "ocr");
    assert.equal(PIPELINE_STAGES[2].id, "document_parsing");
    assert.equal(PIPELINE_STAGES[3].id, "investigation_knowledge_graph");
    assert.equal(PIPELINE_STAGES[4].id, "canonical_investigation");
    assert.equal(PIPELINE_STAGES[5].id, "evidence_validation");
    assert.equal(PIPELINE_STAGES[6].id, "case_context");
    assert.equal(PIPELINE_STAGES[7].id, "legal_reasoning");
    assert.equal(PIPELINE_STAGES[8].id, "chargesheet_population");
  });

  // 12. Validation dispositions are mapped correctly
  it("Requirement 12: Validation artifact returns valid disposition schema", async () => {
    globalThis.fetch = async (url) => {
      assert.ok(url.includes("/artifacts/content/validation_report"));
      return createMockResponse({
        status: 200,
        ok: true,
        json: {
          disposition: "draft_allowed",
          completeness_score: 0.95,
          violations: [],
          rule_results: {
            "RULE_MANDATORY_DOCUMENTS": { passed: true, message: "All documents present" },
          },
        },
        headers: { "content-type": "application/json" },
      });
    };

    const val = await artifactService.getArtifactContent("case-1", "validation_report");
    assert.equal(val.disposition, "draft_allowed");
    assert.equal(val.completeness_score, 0.95);
    assert.equal(val.violations.length, 0);
  });

  // 13. Missing artifacts are handled gracefully
  it("Requirement 13: Missing artifacts return 404 and are caught cleanly", async () => {
    globalThis.fetch = async () => {
      return createMockResponse({
        status: 404,
        ok: false,
        json: { detail: "Artifact 'non_existent' has not been generated for case 'case-1'." },
        headers: { "content-type": "application/json" },
      });
    };

    await assert.rejects(
      async () => await artifactService.getArtifactContent("case-1", "non_existent"),
      (err) => {
        assert.ok(err instanceof APIClientError);
        assert.equal(err.status, 404);
        assert.ok(err.message.includes("has not been generated"));
        return true;
      }
    );
  });

  // 14. PDF download invokes the correct endpoint and constructs URL
  it("Requirement 14: PDF download uses /api/v1/cases/{case_id}/artifacts/chargesheet.pdf", async () => {
    const pdfUrl = artifactService.getDraftPdfUrl("case-download-test");
    assert.ok(pdfUrl.endsWith("/api/v1/cases/case-download-test/artifacts/chargesheet.pdf"));

    globalThis.fetch = async (url) => {
      assert.ok(url.endsWith("/api/v1/cases/case-download-test/artifacts/chargesheet.pdf"));
      return createMockResponse({
        status: 200,
        ok: true,
        text: "%PDF-1.4 test binary stream",
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'inline; filename="draft_chargesheet_case-download-test.pdf"',
        },
      });
    };

    const { blob, filename } = await apiClient.downloadBlob("/api/v1/cases/case-download-test/artifacts/chargesheet.pdf");
    assert.equal(filename, "draft_chargesheet_case-download-test.pdf");
    assert.ok(blob);
  });

  // 15. The existing 3D viewer scenarios registry is accessible
  it("Requirement 15: 3D scenarios registry is intact and contains default cases", async () => {
    const { SCENARIO_REGISTRY } = await import("../src/simulation/scenarios/index.js");
    assert.ok(SCENARIO_REGISTRY);
    assert.ok(SCENARIO_REGISTRY.case_001);
    assert.ok(SCENARIO_REGISTRY.case_001.data);
    assert.ok(SCENARIO_REGISTRY.case_001.data.vehicles.length > 0);
  });

  // 16. No fake cases or fake successful processing states appear by default
  it("Requirement 16: Zero cases returned when backend returns empty case list", async () => {
    globalThis.fetch = async () => {
      return createMockResponse({
        status: 200,
        ok: true,
        json: { cases: [], total: 0 },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await caseService.listCases();
    assert.equal(res.total, 0);
    assert.equal(res.cases.length, 0);
  });

  // 17. Case deletion invokes DELETE /api/v1/cases/{case_id}
  it("Requirement 17: Case deletion invokes DELETE /api/v1/cases/{case_id}", async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes("/api/v1/cases/test-case-delete"));
      assert.equal(options.method, "DELETE");
      return createMockResponse({
        status: 200,
        ok: true,
        json: { case_id: "test-case-delete", status: "deleted", message: "Case permanently deleted." },
        headers: { "content-type": "application/json" },
      });
    };

    const res = await caseService.deleteCase("test-case-delete");
    assert.equal(res.status, "deleted");
    assert.equal(res.case_id, "test-case-delete");
  });
});
