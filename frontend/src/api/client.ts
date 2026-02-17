import type {
  ChapterListResponse,
  DashboardStatsResponse,
  DraftItemsResponse,
  GenerationJobCreateRequest,
  GenerationJobResponse,
  JobListResponse,
  PublishRequest,
  PublishResponse,
  SubjectListResponse,
  TopicListResponse,
  // Sprint 10: New types
  ActivityFeedResponse,
  TokenUsageResponse,
  ReviewQueueResponse,
  CommentListResponse,
  Comment,
  QuestionSearchResponse,
  AnalyticsResponse,
  // User management
  UserResponse,
  UserCreateRequest,
  UserUpdateRequest,
} from "./types";

// Token storage keys (must match AuthContext)
const TOKEN_KEY = 'qbank_auth_token';

async function ensureOk(response: Response): Promise<Response> {
  if (!response.ok) {
    // Handle 401 - redirect to login
    if (response.status === 401) {
      // Clear stored credentials
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('qbank_auth_user');
      // Redirect to login page
      window.location.href = '/login';
      throw new Error('Session expired. Please log in again.');
    }

    let detail = "";
    try {
      const body = await response.clone().json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      detail = "";
    }
    throw new Error(detail ? `Request failed: ${response.status} - ${detail}` : `Request failed: ${response.status}`);
  }
  return response;
}

export class QbankApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string
  ) { }

  private headers(): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    // Prefer JWT token if available
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else if (this.apiKey) {
      // Fall back to internal API key for backward compatibility
      headers["X-Internal-API-Key"] = this.apiKey;
    }

    return headers;
  }

  async createJob(payload: GenerationJobCreateRequest): Promise<GenerationJobResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    return (await ensureOk(response)).json();
  }

  async getJob(jobId: string): Promise<GenerationJobResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async listJobs(limit: number = 20, offset: number = 0): Promise<JobListResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs?limit=${limit}&offset=${offset}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getStats(): Promise<DashboardStatsResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/stats`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getItems(
    jobId: string,
    params: { qc_status?: string; review_status?: string; offset?: number; limit?: number }
  ): Promise<DraftItemsResponse> {
    const query = new URLSearchParams();
    if (params.qc_status) query.set("qc_status", params.qc_status);
    if (params.review_status) query.set("review_status", params.review_status);
    query.set("offset", String(params.offset ?? 0));
    query.set("limit", String(params.limit ?? 50));

    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/items?${query.toString()}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async patchItem(
    jobId: string,
    itemId: number,
    payload: Partial<{
      question: string;
      options: string[];
      correct_answer: string;
      explanation: string;
      cognitive_level: string;
      question_type: string;
      estimated_time: number;
      difficulty: string;
      concepts: string;
      review_status: "pending" | "approved" | "rejected";
    }>
  ) {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/items/${itemId}`, {
      method: "PATCH",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    return (await ensureOk(response)).json();
  }

  async bulkUpdateItems(
    jobId: string,
    itemIds: number[],
    patch: { review_status: string }
  ): Promise<{ updated_count: number; requested_count: number }> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/items/bulk-update`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ item_ids: itemIds, patch }),
    });
    return (await ensureOk(response)).json();
  }

  async publish(jobId: string, payload: PublishRequest): Promise<PublishResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/publish`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    return (await ensureOk(response)).json();
  }

  async restartJob(jobId: string): Promise<GenerationJobResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/restart`, {
      method: "POST",
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async health(): Promise<{ api: string; queue: string }> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/health`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getSubjects(): Promise<SubjectListResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/metadata/subjects`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getChapters(subject?: string): Promise<ChapterListResponse> {
    const query = new URLSearchParams();
    if (subject) query.set("subject", subject);

    const response = await fetch(`${this.baseUrl}/v2/qbank/metadata/chapters?${query.toString()}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getTopics(subject?: string, chapter?: string): Promise<TopicListResponse> {
    const query = new URLSearchParams();
    if (subject) query.set("subject", subject);
    if (chapter) query.set("chapter", chapter);

    const response = await fetch(`${this.baseUrl}/v2/qbank/metadata/topics?${query.toString()}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  // ============================================
  // Sprint 10: New Backend Integration Methods
  // ============================================

  async getActivityFeed(limit: number = 20): Promise<ActivityFeedResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/activity?limit=${limit}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getTokenUsage(days: number = 7): Promise<TokenUsageResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/usage?days=${days}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getReviewQueue(priority?: "urgent" | "normal" | "low", limit: number = 20): Promise<ReviewQueueResponse> {
    const query = new URLSearchParams();
    if (priority) query.set("priority", priority);
    query.set("limit", String(limit));

    const response = await fetch(`${this.baseUrl}/v2/qbank/queue?${query.toString()}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async getItemComments(itemId: number): Promise<CommentListResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/items/${itemId}/comments`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async addItemComment(itemId: number, content: string, parentId?: string): Promise<Comment> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/items/${itemId}/comments`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ content, parent_id: parentId }),
    });
    return (await ensureOk(response)).json();
  }

  async searchQuestions(
    query: string,
    params: { subject?: string; chapter?: string; limit?: number; offset?: number } = {}
  ): Promise<QuestionSearchResponse> {
    const q = new URLSearchParams();
    q.set("query", query);
    if (params.subject) q.set("subject", params.subject);
    if (params.chapter) q.set("chapter", params.chapter);
    q.set("limit", String(params.limit ?? 20));
    q.set("offset", String(params.offset ?? 0));

    const response = await fetch(`${this.baseUrl}/v2/qbank/items/search?${q.toString()}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  /**
   * Export from a specific job. Returns a blob URL for download.
   */
  async exportJob(
    jobId: string,
    params: {
      format: 'pdf' | 'excel' | 'docx' | 'json';
      include_explanations?: boolean;
      include_metadata?: boolean;
      only_approved?: boolean;
    }
  ): Promise<{ blob: Blob; filename: string }> {
    const q = new URLSearchParams();
    q.set("format", params.format);
    q.set("include_explanations", String(params.include_explanations ?? true));
    q.set("include_metadata", String(params.include_metadata ?? false));
    q.set("only_approved", String(params.only_approved ?? true));

    const response = await fetch(`${this.baseUrl}/v2/qbank/jobs/${jobId}/export?${q.toString()}`, {
      headers: this.headers(),
    });
    await ensureOk(response);

    const blob = await response.blob();
    const cd = response.headers.get("Content-Disposition");
    let filename = `qbank_${jobId}.${params.format === 'excel' ? 'xlsx' : params.format}`;
    if (cd) {
      const match = cd.match(/filename="?([^"]+)"?/);
      if (match) filename = match[1];
    }
    return { blob, filename };
  }

  /**
   * Export from the entire library (across all jobs).
   */
  async exportLibrary(
    params: {
      format: 'pdf' | 'excel' | 'docx' | 'json';
      include_explanations?: boolean;
      include_metadata?: boolean;
      only_approved?: boolean;
      subject?: string;
      chapter?: string;
      item_ids?: number[];
    }
  ): Promise<{ blob: Blob; filename: string }> {
    const MIME_TYPES: Record<string, string> = {
      pdf: 'application/pdf',
      excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      json: 'application/json',
    };

    const q = new URLSearchParams();
    q.set("format", params.format);
    q.set("include_explanations", String(params.include_explanations ?? true));
    q.set("include_metadata", String(params.include_metadata ?? false));
    q.set("only_approved", String(params.only_approved ?? true));
    if (params.subject) q.set("subject", params.subject);
    if (params.chapter) q.set("chapter", params.chapter);
    if (params.item_ids?.length) q.set("item_ids", params.item_ids.join(","));

    const response = await fetch(`${this.baseUrl}/v2/qbank/export?${q.toString()}`, {
      headers: this.headers(),
    });
    await ensureOk(response);

    const rawBlob = await response.blob();
    // Ensure correct MIME type — CORS may not expose Content-Type properly
    const blob = new Blob([rawBlob], { type: MIME_TYPES[params.format] || rawBlob.type });

    const cd = response.headers.get("Content-Disposition");
    let filename = `qbank_library.${params.format === 'excel' ? 'xlsx' : params.format}`;
    if (cd) {
      const match = cd.match(/filename="?([^"]+)"?/);
      if (match) filename = match[1];
    }
    return { blob, filename };
  }

  // ============================================
  // Analytics
  // ============================================

  async getAnalytics(days: number = 30): Promise<AnalyticsResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/analytics?days=${days}`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  // ============================================
  // User Management
  // ============================================

  async listUsers(): Promise<UserResponse[]> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/auth/users`, {
      headers: this.headers(),
    });
    return (await ensureOk(response)).json();
  }

  async createUser(payload: UserCreateRequest): Promise<{ user: UserResponse }> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/auth/register`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    return (await ensureOk(response)).json();
  }

  async updateUser(userId: number, payload: UserUpdateRequest): Promise<UserResponse> {
    const response = await fetch(`${this.baseUrl}/v2/qbank/auth/users/${userId}`, {
      method: "PATCH",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    return (await ensureOk(response)).json();
  }
}
