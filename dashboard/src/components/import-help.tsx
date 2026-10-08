import { useState } from 'react'
import { Check, Copy, Terminal } from 'lucide-react'
import { indexCommand } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function ImportHelp({
  repositoryLocation,
}: {
  repositoryLocation: string
}) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  const isRemote = repositoryLocation.includes('://')
  const needsCheckout = !/^(\/|~(\/|$))/.test(repositoryLocation)
  const command = indexCommand(
    needsCheckout ? '/path/to/local/checkout' : repositoryLocation,
  )
  async function copy() {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      setError(false)
    } catch {
      setError(true)
    }
  }
  return (
    <div className="import-help">
      <h3>
        <Terminal size={16} />
        Index from your terminal
      </h3>
      <p>
        {needsCheckout
          ? `This saved location is ${isRemote ? 'a URL' : 'relative'}. Replace the folder below with your local checkout. Indexing creates a folder-based project; open it from All repositories.`
          : 'Run from this app’s directory. The folder must match this repository’s registered location. Each run replaces the saved graph.'}
      </p>
      <div className="command-line">
        <code>{command}</code>
        <Button
          variant="ghost"
          size="icon"
          onClick={copy}
          aria-label="Copy index command"
        >
          {copied ? <Check /> : <Copy />}
        </Button>
      </div>
      <span className="field-help" role="status">
        {error
          ? 'Copy unavailable. Select the command to copy it.'
          : copied
            ? 'Command copied.'
            : 'Index manually, then refresh the graph.'}
      </span>
    </div>
  )
}
