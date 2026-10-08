import { QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'
// TanStack Start's generated Register footer imports getRouter as a type only.
// That erased back-reference is not a runtime cycle; do not hand-edit the tree.
import { routeTree } from './routeTree.gen'

export const getRouter = () =>
  createRouter({
    routeTree,
    context: { queryClient: new QueryClient() },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  })
