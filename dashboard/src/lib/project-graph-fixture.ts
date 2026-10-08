import type { ArtifactNode } from './architecture-artifact'

export function fixtureNodes(): Array<ArtifactNode> {
  const nodes: Array<ArtifactNode> = []
  const byKey = new Map<string, ArtifactNode>()
  const add = (id: string, kind: string, parent: string | null, path = id) => {
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
  add('repo', 'repository', null, '.')
  add('root', 'directory', 'repo', '.')
  add('app', 'directory', 'root')
  add('lib', 'directory', 'root')
  add('pkg', 'directory', 'app')
  add('other', 'directory', 'app')
  add('empty', 'directory', 'app')
  add('java', 'directory', 'pkg')
  add('com', 'directory', 'java')
  add('acme', 'directory', 'com')
  add('service', 'file', 'acme', 'app/pkg/java/com/acme/Service.java')
  add('helper', 'file', 'pkg', 'app/pkg/helper.ts')
  add('other-file', 'file', 'other')
  add('direct', 'file', 'app')
  add('lib-file', 'file', 'lib')
  add('root-file', 'file', 'root')
  add('Service', 'class', 'service')
  Object.assign(
    add('run', 'method', 'Service', 'app/pkg/java/com/acme/Service.java'),
    { startLine: 10, endLine: 20 },
  )
  add('stop', 'method', 'Service')
  add('nested', 'function', 'run')
  add('variable', 'property', 'run')
  add('helper-fn', 'function', 'helper')
  add('other-fn', 'function', 'other-file')
  add('direct-fn', 'function', 'direct')
  add('lib-fn', 'function', 'lib-file')
  add('root-fn', 'function', 'root-file')
  add('external', 'external', 'repo')
  add('external-child', 'function', 'external')
  return nodes
}
