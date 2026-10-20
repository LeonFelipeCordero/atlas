import { FileText, Network } from 'lucide-react'
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
        <Network size={16} aria-hidden="true" /> Explore
      </Button>
      <Button
        variant={mode === 'report' ? 'default' : 'ghost'}
        aria-pressed={mode === 'report'}
        onClick={() => onMode('report')}
      >
        <FileText size={16} aria-hidden="true" /> Report
      </Button>
      <p>
        {mode === 'explore'
          ? 'Explore structure and connections'
          : 'Review findings and measurements'}
      </p>
    </div>
  )
}
