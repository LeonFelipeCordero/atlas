type GraphPosition = { x: number; y: number }

// Route dependency ranks vertically and same-rank connections sideways.
export const getGraphEdgeHandles = (
  source: GraphPosition | undefined,
  target: GraphPosition | undefined,
) => {
  if (!source || !target)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-top' }
  if (target.y > source.y)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-top' }
  if (target.x <= source.x)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-left' }
  if (target.y === source.y)
    return { sourceHandle: 'source-right', targetHandle: 'target-left' }
  return { sourceHandle: 'source-right', targetHandle: 'target-top' }
}
