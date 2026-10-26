import { GRAPH_NODE_HEIGHT, GRAPH_NODE_WIDTH } from './graph-layout'

type GraphPosition = { x: number; y: number }

export type EdgeChannels = {
  sourceRow: number
  targetRow: number
  sourceColumn: number
  targetColumn: number
}

// All edges use the same gap centers; outer turns need room for arrowheads.
function gapCenter(
  value: number,
  size: number,
  values: Array<number>,
  side: 1 | -1,
) {
  const neighbors = values.filter((other) => (other - value) * side > 0)
  const neighbor = side === 1 ? Math.min(...neighbors) : Math.max(...neighbors)
  if (!Number.isFinite(neighbor)) return value + (side === 1 ? size + 40 : -40)
  return (value + size + neighbor) / 2
}

export function getGraphEdgeChannels(
  source: GraphPosition,
  target: GraphPosition,
  positions: Map<string, GraphPosition>,
): EdgeChannels {
  const nodes = [...positions.values()]
  const columns = [...new Set(nodes.map(({ x }) => x))]
  const rows = [...new Set(nodes.map(({ y }) => y))]
  return {
    sourceRow: gapCenter(source.y, GRAPH_NODE_HEIGHT, rows, 1),
    targetRow: gapCenter(target.y, GRAPH_NODE_HEIGHT, rows, -1),
    sourceColumn: gapCenter(source.x, GRAPH_NODE_WIDTH, columns, 1),
    targetColumn: gapCenter(target.x, GRAPH_NODE_WIDTH, columns, -1),
  }
}

export function getGraphEdgePath(
  source: GraphPosition,
  target: GraphPosition,
  sourcePosition: string,
  targetPosition: string,
  channels: EdgeChannels,
) {
  const { sourceRow, targetRow, sourceColumn, targetColumn } = channels
  let bends: Array<GraphPosition>
  if (sourcePosition === 'bottom' && targetPosition === 'top') {
    bends =
      sourceRow === targetRow
        ? [
            { x: source.x, y: sourceRow },
            { x: target.x, y: sourceRow },
          ]
        : [
            { x: source.x, y: sourceRow },
            { x: targetColumn, y: sourceRow },
            { x: targetColumn, y: targetRow },
            { x: target.x, y: targetRow },
          ]
  } else if (sourcePosition === 'bottom') {
    bends = [
      { x: source.x, y: sourceRow },
      { x: targetColumn, y: sourceRow },
      { x: targetColumn, y: target.y },
    ]
  } else {
    bends =
      sourceColumn === targetColumn
        ? []
        : [
            { x: sourceColumn, y: source.y },
            { x: sourceColumn, y: sourceRow },
            { x: targetColumn, y: sourceRow },
            { x: targetColumn, y: target.y },
          ]
  }
  return [source, ...bends, target]
    .map(({ x, y }, index) => `${index === 0 ? 'M' : 'L'}${x} ${y}`)
    .join('')
}

// Forward diagonals use vertical routing; backward edges leave below and enter left.
export const getGraphEdgeHandles = (
  source: GraphPosition | undefined,
  target: GraphPosition | undefined,
) => {
  if (!source || !target)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-top' }
  if (target.y > source.y)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-top' }
  if (target.y === source.y && target.x > source.x)
    return { sourceHandle: 'source-right', targetHandle: 'target-left' }
  return { sourceHandle: 'source-bottom', targetHandle: 'target-left' }
}
