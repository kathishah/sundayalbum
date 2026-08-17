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

// Returns the SHA of the most recent commit touching any of the given paths.
// Commits are stable once merged — no timing sensitivity here.
async function latestRelevantSha(paths: string[]): Promise<string | null> {
  const results = await Promise.allSettled(
    paths.map((p) =>
      ghFetch(
        `/repos/${OWNER}/${REPO}/commits?sha=${branch}&path=${encodeURIComponent(p)}&per_page=1`
      ).then((d) => {
        const commits = d as { sha: string; commit: { committer: { date: string } } }[]
        const c = commits[0]
        return c ? { sha: c.sha, date: c.commit.committer.date } : null
      })
    )
  )
  const entries = results.flatMap((r) =>
    r.status === 'fulfilled' && r.value !== null ? [r.value] : []
  )
  if (entries.length === 0) return null
  // Pick the entry with the most recent commit date, return its SHA
  return entries.sort((a, b) => (a.date < b.date ? 1 : -1))[0].sha
}

// SHA comparison — deterministic, no timestamp race conditions.
function isUpToDate(deployedSha: string | null, latestSha: string | null): boolean | null {
  if (!deployedSha || !latestSha) return null
  return deployedSha === latestSha
}

export async function GET() {
  if (cache && Date.now() - cache.ts < CACHE_TTL_MS) {
    return NextResponse.json(cache.data)
  }

  try {
    const [webRun, backendRun, latestWebSha, latestBackendSha] = await Promise.all([
      getLastSuccessfulRun('deploy-web.yml'),
      getLastSuccessfulRun('deploy-lambda.yml'),
      latestRelevantSha(['web']),
      // api + src cover the vast majority of meaningful backend changes
      latestRelevantSha(['api', 'src']),
    ])

    const data = {
      web: {
        deployed_at: webRun?.deployed_at ?? null,
        // Prefer baked-in SHA (always accurate); fall back to workflow run SHA
        sha: (WEB_BUILD_SHA ?? webRun?.sha)?.slice(0, 7) ?? null,
        // WEB_BUILD_SHA is baked at image build time — never stale, no API lag
        is_latest: isUpToDate(WEB_BUILD_SHA ?? webRun?.sha ?? null, latestWebSha),
      },
      backend: {
        deployed_at: backendRun?.deployed_at ?? null,
        sha: backendRun?.sha.slice(0, 7) ?? null,
        is_latest: isUpToDate(backendRun?.sha ?? null, latestBackendSha),
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
