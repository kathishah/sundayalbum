import { getToken } from '@/lib/auth'
import { API_URL } from '@/lib/constants'
import type {
  AuthResponse,
  ApiKeyStatus,
  CreateJobResponse,
  Job,
  JobsResponse,
  ReprocessRequest,
  ReprocessResponse,
  StartJobResponse,
} from '@/lib/types'

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.message ?? body.error ?? message
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function sendCode(email: string): Promise<{ message: string }> {
  return apiFetch('/auth/send-code', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function verifyCode(
  email: string,
  code: string,
): Promise<AuthResponse> {
  return apiFetch('/auth/verify', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  })
}

export async function logout(): Promise<void> {
  return apiFetch('/auth/logout', { method: 'POST' })
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export async function listJobs(): Promise<JobsResponse> {
  return apiFetch('/jobs')
}

export async function createJob(
  filename: string,
  size: number,
): Promise<CreateJobResponse> {
  return apiFetch('/jobs', {
    method: 'POST',
    body: JSON.stringify({ filename, size }),
  })
}

export async function getJob(jobId: string): Promise<Job> {
  return apiFetch(`/jobs/${jobId}`)
}

export async function deleteJob(jobId: string): Promise<void> {
  return apiFetch(`/jobs/${jobId}`, { method: 'DELETE' })
}

export async function startJob(jobId: string): Promise<StartJobResponse> {
  return apiFetch(`/jobs/${jobId}/start`, { method: 'POST' })
}

export async function reprocessJob(
  jobId: string,
  req: ReprocessRequest,
): Promise<ReprocessResponse> {
  return apiFetch(`/jobs/${jobId}/reprocess`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ── Settings ──────────────────────────────────────────────────────────────────

export async function getApiKeys(): Promise<ApiKeyStatus> {
  return apiFetch('/settings/api-keys')
}

export async function updateApiKeys(keys: {
  anthropic_api_key?: string
  openai_api_key?: string
}): Promise<void> {
  return apiFetch('/settings/api-keys', {
    method: 'PUT',
    body: JSON.stringify(keys),
  })
}

export async function deleteApiKeys(): Promise<void> {
  return apiFetch('/settings/api-keys', { method: 'DELETE' })
}

// ── S3 direct upload ──────────────────────────────────────────────────────────

export async function s3Upload(url: string, file: File): Promise<void> {
  const res = await fetch(url, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
    },
  })

  if (!res.ok) {
    throw new ApiError(res.status, `S3 upload failed: HTTP ${res.status}`)
  }
}

export { ApiError }
