import { create } from 'zustand'
import type { Job } from '@/lib/types'

interface JobsState {
  jobs: Job[]
  setJobs: (jobs: Job[]) => void
  upsertJob: (job: Job) => void
  removeJob: (jobId: string) => void
}

export const useJobsStore = create<JobsState>((set) => ({
  jobs: [],
  setJobs: (jobs: Job[]) => set({ jobs }),
  upsertJob: (job: Job) =>
    set((state) => {
      const idx = state.jobs.findIndex((j) => j.job_id === job.job_id)
      if (idx === -1) {
        return { jobs: [job, ...state.jobs] }
      }
      const next = [...state.jobs]
      next[idx] = { ...next[idx], ...job }
      return { jobs: next }
    }),
  removeJob: (jobId: string) =>
    set((state) => ({
      jobs: state.jobs.filter((j) => j.job_id !== jobId),
    })),
}))
