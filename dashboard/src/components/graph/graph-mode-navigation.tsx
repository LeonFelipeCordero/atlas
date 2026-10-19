import { Button } from '@/components/ui/button'

export type WorkspaceMode = 'explore' | 'report'

export function GraphModeNavigation({
  mode,
  onMode,
}: {
  mode: WorkspaceMode
  onMode: (mode: WorkspaceMode) => void
}) {
  return (
    <div className="workspace-modes" role="group" aria-label="Workspace mode">
      <Button
        variant={mode === 'explore' ? 'default' : 'ghost'}
        aria-pressed={mode === 'explore'}
        onClick={() => onMode('explore')}
      >
        Explore
      </Button>
      <Button
        variant={mode === 'report' ? 'default' : 'ghost'}
        aria-pressed={mode === 'report'}
        onClick={() => onMode('report')}
      >
        Report
      </Button>
      <p>
        {mode === 'explore'
          ? 'Structure and connections'
          : 'Analysis from the saved index'}
      </p>
    </div>
  )
}
