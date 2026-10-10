import type { ArtifactNode } from '@/lib/architecture-artifact'

export function GraphDependencyMetrics({ node }: { node: ArtifactNode }) {
  const instability = node.properties?.instability
  const rows = [
    ['Fan-in', node.properties?.fanIn, 'Distinct direct dependents'],
    ['Fan-out', node.properties?.fanOut, 'Distinct direct dependencies'],
    [
      'Internal instability',
      instability === null ? 'N/A' : instability?.toFixed(2),
      'Fan-out / (fan-in + fan-out); N/A for isolated items',
    ],
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
            Counts distinct internal {node.level} peers across the full index,
            including tests and type-only dependencies. Self and external
            dependencies are excluded. Internal instability is fan-out / (fan-in
            + fan-out); N/A means isolated. Impact follows direct and indirect
            dependents, excluding this item.
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
