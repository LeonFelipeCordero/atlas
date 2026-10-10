import { sumFileComplexity } from './file-complexity'
import type { Artifact } from './architecture-artifact'
import type { GraphDetails } from './graph-data'

export const fixtureDetails = (artifact: Artifact): GraphDetails => ({
  nodes: artifact.nodes,
  fileComplexities: Object.fromEntries(
    artifact.nodes
      .filter((node) => node.level === 'file')
      .map((node) => [
        node.stableKey,
        sumFileComplexity(artifact, node.stableKey),
      ]),
  ),
})
