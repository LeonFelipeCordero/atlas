import { useState } from 'react'
import { Check, Copy, Terminal } from 'lucide-react'
import { indexCommand } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function ImportHelp({ repositoryName }: { repositoryName: string }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(indexCommand(repositoryName))
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
        Run from this app’s directory. Replace{' '}
        <code>&lt;repository-path&gt;</code> with your local source directory.
        Each run replaces the saved graph.
      </p>
      <div className="command-line">
        <code>{indexCommand(repositoryName)}</code>
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
            ? 'Command copied. Replace the directory placeholder before running.'
            : 'Index manually, then refresh the graph.'}
      </span>
    </div>
  )
}
