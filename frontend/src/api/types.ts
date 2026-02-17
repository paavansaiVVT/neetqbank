export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "publishing"
  | "published";

export type ReviewStatus = "pending" | "approved" | "rejected";
export type QCStatus = "pass" | "fail";

export interface DifficultyDistribution {
  easy: number;
  medium: number;
  hard: number;
  veryhard: number;
}

export interface GenerationJobCreateRequest {
  selected_subject: string;
  selected_chapter: string;
  selected_input: string;
  difficulty: "easy" | "medium" | "hard" | "veryhard" | DifficultyDistribution;
  count: number;
  requested_by: string;
  cognitive?: Record<string, number>; // Allow cognitive distribution
  question_types?: Record<string, number>;
  batch_name?: string;
  generation_model?: string;
  qc_model?: string;
}

export interface GenerationJobResponse {
  job_id: string;
  status: JobStatus;
  progress_percent: number;
  requested_count: number;
  generated_count: number;
  passed_count: number;
  failed_count: number;
  retry_count: number;
  token_usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    input_cost?: number;
    output_cost?: number;
    total_cost?: number;
  };
  timestamps: {
    created_at: string;
    updated_at: string;
    started_at: string | null;
    completed_at: string | null;
    published_at: string | null;
  };
  error: { message?: string; traceback?: string } | null;
  // Included from API but maybe optional in type
  selected_subject?: string;
  selected_chapter?: string;
  selected_input?: string;
  difficulty?: string;
}

export interface JobListResponse {
  items: GenerationJobResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardStatsResponse {
  total_jobs: number;
  completed_jobs: number;
  total_questions: number;
  passed_questions: number;
  pass_rate: number;
  token_usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
}

export interface DraftQuestionItem {
  item_id: number;
  job_id: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  cognitive_level: string;
  question_type: string;
  estimated_time: number | null;
  difficulty?: string; // Made optional as it's missing in API response sample
  concepts: string | null;
  qc_status: QCStatus;
  review_status: ReviewStatus;
  scores: Record<string, unknown> | null;
  recommendations: unknown;
  violations: unknown;
  category_scores: Record<string, unknown> | null;
  edited: boolean;
  published: boolean;
  published_question_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface DraftItemsResponse {
  items: DraftQuestionItem[];
  total: number;
  offset: number;
  limit: number;
  // Deprecated/Legacy fields if any
}

export interface PublishRequest {
  publish_mode: "selected" | "all_approved";
  item_ids?: number[];
}

export interface PublishResponse {
  published_count: number;
  skipped_count: number;
  failed_count: number;
  published_question_ids: number[];
}

export interface SubjectListResponse {
  subjects: string[];
}

export interface ChapterListResponse {
  chapters: string[];
}

export interface TopicListResponse {
  topics: string[];
}


// ============================================
// Sprint 10: New Backend Integration Types
// ============================================

export type ActivityType =
  | "created"
  | "approved"
  | "rejected"
  | "edited"
  | "commented"
  | "published"
  | "generated";

export interface ActivityItem {
  id: string;
  activity_type: ActivityType;
  user_id: string;
  user_name: string;
  target_type: string;
  target_id: string;
  target_label: string;
  details?: string;
  timestamp: string;
}

export interface ActivityFeedResponse {
  items: ActivityItem[];
  total: number;
}

export interface DailyUsage {
  date: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  cost_inr?: number;
  generation_tokens?: number;
  qc_tokens?: number;
}

export interface TokenUsageResponse {
  daily_usage: DailyUsage[];
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_cost_inr?: number;
  period_days: number;
}

export type QueueItemPriority = "urgent" | "normal" | "low";

export interface QueueItem {
  id: number;
  job_id: string;
  question: string;
  subject: string;
  chapter: string;
  priority: QueueItemPriority;
  assigned_at: string;
  due_at?: string;
}

export interface ReviewQueueResponse {
  items: QueueItem[];
  total: number;
}

export interface Comment {
  id: string;
  item_id: number;
  user_id: string;
  user_name: string;
  content: string;
  created_at: string;
  parent_id?: string;
}

export interface CommentListResponse {
  comments: Comment[];
  total: number;
}

export interface SearchResultItem {
  item_id: number;
  job_id: string;
  question: string;
  subject: string;
  chapter: string;
  difficulty: string;
  similarity_score?: number;
}

export interface QuestionSearchResponse {
  items: SearchResultItem[];
  total: number;
  query: string;
}


// ============================================
// Analytics Types
// ============================================

export interface AnalyticsSummary {
  total_mcqs: number;
  mcqs_this_week: number;
  approval_rate: number;
  rejection_rate: number;
  total_cost_usd: number;
  published_count: number;
}

export interface DailyTrendItem {
  date: string;
  count: number;
  cost: number;
}

export interface SubjectBreakdown {
  subject: string;
  count: number;
}

export interface ChapterBreakdown {
  subject: string;
  chapter: string;
  count: number;
}

export interface UserAnalytics {
  user_id: string;
  user_name: string;
  count: number;
  approval_rate: number;
  cost: number;
}

export interface AnalyticsResponse {
  summary: AnalyticsSummary;
  daily_trend: DailyTrendItem[];
  by_subject: SubjectBreakdown[];
  by_chapter: ChapterBreakdown[];
  by_difficulty: Record<string, number>;
  by_cognitive: Record<string, number>;
  by_user: UserAnalytics[];
  model_usage: Record<string, number>;
}


// ============================================
// User Management Types
// ============================================

export type UserRole = "creator" | "reviewer" | "publisher" | "admin";

export interface UserResponse {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  created_at: string;
  is_active: boolean;
}

export interface UserCreateRequest {
  email: string;
  password: string;
  name: string;
  role: UserRole;
}

export interface UserUpdateRequest {
  role?: UserRole;
  is_active?: boolean;
  name?: string;
}

