import type { ArtifactNode } from './architecture-artifact'

type FixtureNode = {
  id: string
  kind: string
  parent: string | null
  path?: string
}

export function fixtureNodes(): Array<ArtifactNode> {
  const nodes: Array<ArtifactNode> = []
  const byKey = new Map<string, ArtifactNode>()
  const add = ({ id, kind, parent, path = id }: FixtureNode) => {
    const owner = parent === null ? undefined : byKey.get(parent)
    const level =
      (
        {
          directory: 'module',
          class: 'type',
          method: 'callable',
          function: 'callable',
          property: 'symbol',
        } as Record<string, string>
      )[kind] ?? kind
    const node: ArtifactNode = {
      stableKey: id,
      type: kind === 'directory' ? 'module' : kind,
      kind,
      level,
      name: id.split('/').at(-1)!,
      path,
      language: null,
      parentStableKey: parent,
      ancestorStableKeys: owner
        ? [...owner.ancestorStableKeys, owner.stableKey]
        : [],
      depth: owner ? owner.depth + 1 : 0,
    }
    nodes.push(node)
    byKey.set(id, node)
    return node
  }
  add({ id: 'repo', kind: 'repository', parent: null, path: '.' })
  add({ id: 'root', kind: 'directory', parent: 'repo', path: '.' })
  add({ id: 'app', kind: 'directory', parent: 'root' })
  add({ id: 'lib', kind: 'directory', parent: 'root' })
  add({ id: 'pkg', kind: 'directory', parent: 'app' })
  add({ id: 'other', kind: 'directory', parent: 'app' })
  add({ id: 'empty', kind: 'directory', parent: 'app' })
  add({ id: 'java', kind: 'directory', parent: 'pkg' })
  add({ id: 'com', kind: 'directory', parent: 'java' })
  add({ id: 'acme', kind: 'directory', parent: 'com' })
  add({
    id: 'service',
    kind: 'file',
    parent: 'acme',
    path: 'app/pkg/java/com/acme/Service.java',
  })
  add({ id: 'helper', kind: 'file', parent: 'pkg', path: 'app/pkg/helper.ts' })
  add({ id: 'other-file', kind: 'file', parent: 'other' })
  add({ id: 'direct', kind: 'file', parent: 'app' })
  add({ id: 'lib-file', kind: 'file', parent: 'lib' })
  add({ id: 'root-file', kind: 'file', parent: 'root' })
  add({ id: 'Service', kind: 'class', parent: 'service' })
  Object.assign(
    add({
      id: 'run',
      kind: 'method',
      parent: 'Service',
      path: 'app/pkg/java/com/acme/Service.java',
    }),
    { startLine: 10, endLine: 20 },
  )
  add({ id: 'stop', kind: 'method', parent: 'Service' })
  add({ id: 'nested', kind: 'function', parent: 'run' })
  add({ id: 'variable', kind: 'property', parent: 'run' })
  add({ id: 'helper-fn', kind: 'function', parent: 'helper' })
  add({ id: 'other-fn', kind: 'function', parent: 'other-file' })
  add({ id: 'direct-fn', kind: 'function', parent: 'direct' })
  add({ id: 'lib-fn', kind: 'function', parent: 'lib-file' })
  add({ id: 'root-fn', kind: 'function', parent: 'root-file' })
  add({ id: 'external', kind: 'external', parent: 'repo' })
  add({ id: 'external-child', kind: 'function', parent: 'external' })
  return nodes
}
