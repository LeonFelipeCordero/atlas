import { ReportFindings } from './report-findings'
import { ReportItems } from './report-items'
import type { ReportItemProps } from './report-items'
import type { ViewCycle } from '@/lib/graph-data'
import { Button } from '@/components/ui/button'

export function GraphReport({
  onCycleScope,
  ...props
}: ReportItemProps & {
  onCycleScope: (cycle: ViewCycle) => void
}) {
  const { view, onExplore } = props
  const path = view.trail.map((part) => part.label).join(' / ')
  return (
    <div className="report-workspace">
      <header className="report-intro">
        <div>
          <h2>Report</h2>
          <p>{path}</p>
        </div>
        <Button variant="outline" onClick={() => onExplore()}>
          Explore this scope
        </Button>
      </header>
      <div className="report-body">
        <ReportFindings view={view} onCycleScope={onCycleScope} />
        <details className="report-source report-coverage">
          <summary>Scope and measurement coverage</summary>
          <p>
            This report uses the saved index imported{' '}
            {new Date(view.importedAt).toLocaleString()}. It does not inspect
            current source files.
          </p>
          <p>
            {view.details.nodes.length} item records available at this level.
            Open a folder or file report to inspect its children. Conventional
            test files are hidden from navigation. Outside-repository references
            are excluded; outgoing internal references outside this scope appear
            separately.
          </p>
          <p>
            Dependency metrics use the full index, including tests and type-only
            dependencies. File complexity sums include owned functions and
            methods. Missing values are not zero. Thresholds are unavailable
            here.
          </p>
        </details>
        <ReportItems {...props} />
      </div>
    </div>
  )
}
