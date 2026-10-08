import { ChevronRight } from 'lucide-react'
import type { GraphScope } from '@/lib/project-graph'

export type GraphTrail = { label: string; scope: GraphScope }

type Props = {
  trail: Array<GraphTrail>
  navigate: (index: number) => void
}

export function GraphNavigation({ trail, navigate }: Props) {
  return (
    <nav
      aria-label="Graph breadcrumbs"
      className="explorer-navigation graph-breadcrumbs"
    >
      {trail.map((entry, index) => (
        <span
          key={entry.scope.kind === 'repository' ? 'root' : entry.scope.key}
        >
          {index > 0 && <ChevronRight size={14} />}
          <button
            onClick={() => navigate(index)}
            aria-current={index === trail.length - 1 ? 'location' : undefined}
          >
            {entry.label}
          </button>
        </span>
      ))}
    </nav>
  )
}
