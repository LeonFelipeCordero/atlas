import type { ArtifactNode } from './architecture-artifact'

/** Queue children without spreading unbounded sibling lists into call arguments. */
export function pushChildren(
  pending: Array<ArtifactNode>,
  children: Array<ArtifactNode>,
  reverse = false,
) {
  for (let index = 0; index < children.length; index++)
    pending.push(children[reverse ? children.length - 1 - index : index])
}
