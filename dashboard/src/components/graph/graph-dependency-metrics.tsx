import type { ArtifactNode } from '@/lib/architecture-artifact'

export function GraphDependencyMetrics({ node }: { node: ArtifactNode }) {
  const rows = [
    ['Fan-in', node.properties?.fanIn, 'Distinct direct dependents'],
    ['Fan-out', node.properties?.fanOut, 'Distinct direct dependencies'],
    [
      'Transitive change impact',
      node.properties?.transitiveChangeImpact,
      'Distinct direct and indirect dependents, excluding this item',
    ],
  ] as const
  const available = rows.some(([, value]) => value !== undefined)
  return (
    <section className="node-complexity" aria-label="Dependency metrics">
      <h4>Dependency metrics</h4>
      {available ? (
        <>
          <dl>
            {rows.map(([label, value, description]) => (
              <div key={label}>
                <dt title={description}>{label}</dt>
                <dd>{value ?? 'Not indexed'}</dd>
              </div>
            ))}
          </dl>
          <p className="sidebar-hint">
            Counts distinct {node.level} peers across the full index, including
            tests and type-only dependencies. Impact follows direct and indirect
            dependents; it excludes this item. External targets are excluded.
          </p>
        </>
      ) : (
        <p className="sidebar-hint">
          Not available. Re-index this repository to include dependency metrics.
        </p>
      )}
    </section>
  )
}
