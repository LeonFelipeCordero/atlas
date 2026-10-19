import { Suspense, lazy } from 'react'
import { Network } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'

const GraphCanvas = lazy(() => import('./graph-canvas'))

function EmptyGraph({ isFile, back }: { isFile: boolean; back?: () => void }) {
  return (
    <div className="empty-graph">
      <Network size={32} />
      <h3>
        {isFile
          ? 'No functions in this file'
          : 'Nothing indexed in this folder'}
      </h3>
      <p>
        {isFile
          ? 'Configuration, styles, and documentation may not contain callable symbols.'
          : 'Only items recorded in the saved index appear here.'}
      </p>
      {back && (
        <Button variant="outline" onClick={back}>
          Back to parent
        </Button>
      )}
    </div>
  )
}

export function GraphViewport({
  isFile,
  back,
  ...props
}: ComponentProps<typeof GraphCanvas> & {
  isFile: boolean
  back?: () => void
}) {
  if (!props.graph.nodes.length)
    return <EmptyGraph isFile={isFile} back={back} />
  return (
    <Suspense
      fallback={
        <div className="loading-state" role="status">
          Drawing your graph…
        </div>
      }
    >
      <GraphCanvas {...props} />
    </Suspense>
  )
}
