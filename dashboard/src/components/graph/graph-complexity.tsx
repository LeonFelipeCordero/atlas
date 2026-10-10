import type { NodeComplexity } from '@/lib/architecture-artifact'

export function GraphComplexity({
  properties,
}: {
  properties?: NodeComplexity
}) {
  const total = properties?.cyclomaticComplexity
  const rows = [
    ['Cyclomatic complexity', properties?.baseCyclomaticComplexity],
    ['Nested decisions extra', properties?.nestedCyclomaticComplexity],
    ['Nested loops extra', properties?.loopNestedComplexity],
    ['Maximum decision depth', properties?.maxDecisionDepth],
  ] as const
  return (
    <section className="node-complexity" aria-label="Weighted complexity">
      <h4>Weighted complexity</h4>
      {total === undefined ? (
        <p className="sidebar-hint">
          Not available. Re-index this repository to include complexity.
        </p>
      ) : (
        <dl>
          <div className="complexity-total">
            <dt>Total</dt>
            <dd>{total}</dd>
          </div>
          {rows.map(
            ([label, value]) =>
              value !== undefined && (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ),
          )}
        </dl>
      )}
    </section>
  )
}
