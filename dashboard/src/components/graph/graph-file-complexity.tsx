import type { FileComplexitySum } from '@/lib/file-complexity'

function complexityHint(
  sum: FileComplexitySum,
  unavailable: boolean,
  partial: boolean,
) {
  if (unavailable)
    return 'Re-index and import this repository to include complexity.'
  if (partial)
    return `${sum.measured} of ${sum.functions} functions/methods measured. Re-index and import for a complete sum.`
  return `Sum of total complexity across ${sum.functions} ${sum.functions === 1 ? 'function/method' : 'functions/methods'} in this file.`
}

export function GraphFileComplexity({
  sum,
  compact = false,
}: {
  sum: FileComplexitySum
  compact?: boolean
}) {
  const unavailable = sum.functions > 0 && sum.measured === 0
  const partial = sum.measured < sum.functions
  return (
    <section
      className={`file-complexity ${compact ? 'file-complexity-bar' : 'node-complexity'}`}
      aria-label="File function complexity sum"
    >
      <h4>Function complexity sum</h4>
      <p className="file-complexity-value">
        <strong>{unavailable ? 'Not available' : sum.total}</strong>
        {!unavailable && partial && <span>Partial sum</span>}
      </p>
      <p className="sidebar-hint">
        {complexityHint(sum, unavailable, partial)}
      </p>
    </section>
  )
}
