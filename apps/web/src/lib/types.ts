export type JobStatus = 'uploading' | 'processing' | 'complete' | 'failed'

export interface Job {
  job_id: string
  status: JobStatus
  current_step: string
  step_detail: string
  input_filename: string
  input_stem: string
  photo_count: number
  created_at: string
  updated_at: string
  error_message: string
  processing_time: number
  output_keys: string[]
  output_urls?: string[]
  debug_urls?: Record<string, string>      // label → presigned S3 URL for full-res debug image
  upload_url?: string
  /** 400px thumbnail of the original input (01_loaded). Returned by both
   *  GET /jobs (list) and GET /jobs/{id} so card before-thumbnails render
   *  without a separate getJob fetch. Expires in 7 days. */
  thumbnail_url?: string
  /** All step thumbnails (same label namespace as debug_urls). Only returned
   *  by GET /jobs/{id} — used by the Phase 5 step-detail page. */
  thumbnail_urls?: Record<string, string>
  /** Client-only: object URL from the uploaded File, used as before-thumbnail
   *  placeholder until thumbnail_url arrives from the backend. */
  preview_url?: string
}

export interface StepUpdate {
  type: 'step_update'
  jobId: string
  status: JobStatus
  step: string
  detail: string
  progress: number
  photoCount: number
}

export interface ApiKeyStatus {
  has_anthropic_key: boolean
  has_openai_key: boolean
}

export interface AuthResponse {
  session_token: string
  user_hash: string
  expires_at: string
}

export interface CreateJobResponse {
  job_id: string
  upload_url: string
  upload_key: string
  expires_in: number
}

export interface JobsResponse {
  jobs: Job[]
  count: number
}

export interface StartJobResponse {
  status: string
  execution_arn: string
}

export interface ReprocessRequest {
  from_step: string
  photo_index?: number
  config?: Record<string, unknown>
}

export interface ReprocessResponse {
  status: string
  execution_arn: string
  from_step: string
}
