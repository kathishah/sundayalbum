import { Suspense } from 'react'
import PipelinePageContent from './_content'

export default function PipelinePage() {
  return (
    <Suspense
      fallback={
        <div className="py-24 px-4 text-center text-sa-stone-400 dark:text-sa-stone-500">
          Loading…
        </div>
      }
    >
      <PipelinePageContent />
    </Suspense>
  )
}
