type GraphPosition = { x: number; y: number }

// Preserve the /architecture routing rules from doc-gen commit 80465e3.
export const getGraphEdgeHandles = (
  source: GraphPosition | undefined,
  target: GraphPosition | undefined,
) => {
  if (!source || !target)
    return { sourceHandle: 'source-right', targetHandle: 'target-left' }
  if (target.x > source.x)
    return { sourceHandle: 'source-right', targetHandle: 'target-left' }
  if (target.y <= source.y)
    return { sourceHandle: 'source-right', targetHandle: 'target-top' }
  if (target.x === source.x)
    return { sourceHandle: 'source-bottom', targetHandle: 'target-top' }
  return { sourceHandle: 'source-bottom', targetHandle: 'target-left' }
}
