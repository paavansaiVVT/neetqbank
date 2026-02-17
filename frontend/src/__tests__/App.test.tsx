import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "../App";

function mockJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a job and shows job metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/v2/qbank/metadata/subjects")) {
        return mockJsonResponse({ subjects: ["Physics"] });
      }
      if (url.includes("/v2/qbank/metadata/chapters")) {
        return mockJsonResponse({ chapters: ["Laws of Motion"] });
      }
      if (url.includes("/v2/qbank/metadata/topics")) {
        return mockJsonResponse({ topics: ["Friction"] });
      }
      if (url.endsWith("/v2/qbank/jobs") && init?.method === "POST") {
        return mockJsonResponse({
          job_id: "job-1",
          status: "queued",
          progress_percent: 0,
          requested_count: 10,
          generated_count: 0,
          passed_count: 0,
          failed_count: 0,
          retry_count: 0,
          token_usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
          timestamps: {
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-01T00:00:00",
            started_at: null,
            completed_at: null,
            published_at: null,
          },
          error: null,
        });
      }
      if (url.includes("/v2/qbank/jobs/job-1")) {
        return mockJsonResponse({
          job_id: "job-1",
          status: "queued",
          progress_percent: 0,
          requested_count: 10,
          generated_count: 0,
          passed_count: 0,
          failed_count: 0,
          retry_count: 0,
          token_usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
          timestamps: {
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-01T00:00:00",
            started_at: null,
            completed_at: null,
            published_at: null,
          },
          error: null,
        });
      }
      return mockJsonResponse({}, 404);
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByLabelText(/select topics/i)).toHaveValue("Friction");
    });

    const formSection = screen
      .getByRole("heading", { name: /generate questions form/i })
      .closest("section");
    if (!formSection) {
      throw new Error("Generate Questions form section not found");
    }

    await userEvent.click(
      within(formSection).getByRole("button", { name: /^generate questions$/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/job job-1 created\./i)).toBeInTheDocument();
      expect(screen.getByText("Job job-1")).toBeInTheDocument();
    });

    expect(
      fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/v2/qbank/jobs") && init?.method === "POST")
    ).toBe(true);
  });

  it("blocks invalid count before API call", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/v2/qbank/metadata/subjects")) {
        return mockJsonResponse({ subjects: ["Physics"] });
      }
      if (url.includes("/v2/qbank/metadata/chapters")) {
        return mockJsonResponse({ chapters: ["Laws of Motion"] });
      }
      if (url.includes("/v2/qbank/metadata/topics")) {
        return mockJsonResponse({ topics: ["Friction"] });
      }
      return mockJsonResponse({}, 404);
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByLabelText(/select topics/i)).toHaveValue("Friction");
    });

    const countInput = screen.getByLabelText(/total questions/i);
    await userEvent.clear(countInput);
    await userEvent.type(countInput, "0");
    const formSection = screen
      .getByRole("heading", { name: /generate questions form/i })
      .closest("section");
    if (!formSection) {
      throw new Error("Generate Questions form section not found");
    }
    await userEvent.click(
      within(formSection).getByRole("button", { name: /^generate questions$/i })
    );

    await waitFor(() => {
      const jobCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/v2/qbank/jobs"));
      expect(jobCalls).toHaveLength(0);
    });
    expect(countInput).toBeInvalid();
  });
});
