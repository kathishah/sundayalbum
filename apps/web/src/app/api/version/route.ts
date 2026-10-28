import { NextResponse } from 'next/server'

const OWNER = 'kathishah'
const REPO = 'sundayalbum'
const GH_BASE = 'https://api.github.com'
const GH_HEADERS = {
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
}

// In-memory cache — shared across requests within an App Runner instance.
// 10-minute TTL keeps GitHub API usage well under the 60 req/hour unauthenticated limit.
const CACHE_TTL_MS = 10 * 60 * 1000

interface DeployInfo {
  deployed_at: string | null
  sha: string | null
  is_latest: boolean | null
}

interface CacheEntry {
  data: { web: DeployInfo; backend: DeployInfo }
  ts: number
}

let cache: CacheEntry | null = null

const stage = process.env.NEXT_PUBLIC_STAGE ?? 'dev'
const branch = stage === 'prod' ? 'main' : 'dev'

// The SHA baked into this image at Docker build time — always correct, no API lag.
const WEB_BUILD_SHA = process.env.NEXT_PUBLIC_BUILD_SHA ?? null

async function ghFetch(path: string): Promise<unknown> {
  const res = await fetch(`${GH_BASE}${path}`, { headers: GH_HEADERS })
  if (!res.ok) throw new Error(`GitHub API ${path} → ${res.status}`)
  return res.json()
}

async function getLastSuccessfulRun(
  workflow: string
): Promise<{ deployed_at: string; sha: string } | null> {
  const data = (await ghFetch(
    `/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?branch=${branch}&status=success&per_page=1`
  )) as { workflow_runs?: { updated_at: string; head_sha: string }[] }
  const run = data.workflow_runs?.[0]
  if (!run) return null
  return { deployed_at: run.updated_at, sha: run.head_sha }
}

// Paths whose changes trigger each deploy workflow (keep in sync with the
// `paths:` filters in .github/workflows/deploy-web.yml and deploy-lambda.yml).
const WEB_PATHS = ['apps/web/', '.github/workflows/deploy-web.yml']
const BACKEND_PATHS = [
  'services/api/',
  'services/handlers/',
  'packages/pipeline/',
  'Dockerfile',
  '.github/workflows/deploy-lambda.yml',
]

// GitHub's compare endpoint returns at most 300 files per response.
const COMPARE_FILE_LIMIT = 300

// A component is up to date when no commit between the deployed SHA and the branch
// tip changed any of its paths. Comparing ancestry (not SHA equality) is what makes
// this correct: merge-commit promotions and docs-only merges move the branch tip
// without redeploying, and the deployed SHA is rarely the last commit touching a path.
// Returns null (badge hidden) when the answer is unknown.
async function isUpToDate(deployedSha: string | null, paths: string[]): Promise<boolean | null> {
  if (!deployedSha) return null
  try {
    const cmp = (await ghFetch(`/repos/${OWNER}/${REPO}/compare/${deployedSha}...${branch}`)) as {
      files?: { filename: string }[]
    }
    const files = cmp.files
    if (!files) return null
    if (files.some((f) => paths.some((p) => f.filename.startsWith(p)))) return false
    // No match, but the file list may be truncated: we cannot rule out a later match.
    return files.length >= COMPARE_FILE_LIMIT ? null : true
  } catch (err) {
    console.error('Version compare failed:', err)
    return null
  }
}

export async function GET() {
  if (cache && Date.now() - cache.ts < CACHE_TTL_MS) {
    return NextResponse.json(cache.data)
  }

  try {
    const [webRun, backendRun] = await Promise.all([
      getLastSuccessfulRun('deploy-web.yml'),
      getLastSuccessfulRun('deploy-lambda.yml'),
    ])
    const webSha = WEB_BUILD_SHA ?? webRun?.sha ?? null
    const [webLatest, backendLatest] = await Promise.all([
      isUpToDate(webSha, WEB_PATHS),
      isUpToDate(backendRun?.sha ?? null, BACKEND_PATHS),
    ])

    const data = {
      web: {
        deployed_at: webRun?.deployed_at ?? null,
        // Prefer baked-in SHA (always accurate); fall back to workflow run SHA
        sha: (WEB_BUILD_SHA ?? webRun?.sha)?.slice(0, 7) ?? null,
        // WEB_BUILD_SHA is baked at image build time — never stale, no API lag
        is_latest: webLatest,
      },
      backend: {
        deployed_at: backendRun?.deployed_at ?? null,
        sha: backendRun?.sha.slice(0, 7) ?? null,
        is_latest: backendLatest,
      },
    }

    cache = { data, ts: Date.now() }
    return NextResponse.json(data)
  } catch (err) {
    console.error('Version check failed:', err)
    if (cache) return NextResponse.json(cache.data)
    return NextResponse.json({ error: 'unavailable' }, { status: 503 })
  }
}
