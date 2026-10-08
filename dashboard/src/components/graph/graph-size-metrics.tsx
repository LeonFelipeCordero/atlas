import type { ArtifactNode } from '@/lib/architecture-artifact'

export function GraphSizeMetrics({ node }: { node: ArtifactNode }) {
  const callable = ['function', 'method'].includes(node.kind)
  if (node.kind !== 'file' && !callable) return null
  const rows = [
    ['Lines', node.properties?.lineCount],
    ...(callable
      ? [['Parameters', node.properties?.parameterCount] as const]
      : []),
  ] as const
  const available = rows.some(([, value]) => value !== undefined)
  return (
    <section className="node-complexity" aria-label="Size metrics">
      <h4>Size</h4>
      {available ? (
        <>
          <dl>
            {rows.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value ?? 'Not available'}</dd>
              </div>
            ))}
          </dl>
          <p className="sidebar-hint">
            {callable
              ? 'Physical declaration lines, including comments and blanks. Parameters exclude receivers; unavailable counts are not zero.'
              : 'Physical file lines, including comments and blanks.'}
          </p>
        </>
      ) : (
        <p className="sidebar-hint">
          Not available. Re-index this repository to include size metrics.
        </p>
      )}
    </section>
  )
}
