# Autonomous mutation execution

Configure trusted test commands in the project-root `atlas.json`. Atlas does not
create a workspace, discover targets, or run unchanged tests first. Prepare your
environment and confirm that your selected tests pass before starting.

```json
{
  "mutations": {
    "rules": ["comparison.less-to-less-equal"],
    "targets": {
      "module-a": {
        "sources": ["src/module_a/**"],
        "cwd": ".",
        "command": ["pytest", "tests/module_a"],
        "timeoutSeconds": 120
      }
    }
  }
}
```

Source patterns match project-relative POSIX paths with shell-style wildcards.
Only `**` crosses directory separators. Use `src/package/**` for a subtree.
Patterns select source paths, not test paths. Multiple matching targets all run.
Unmatched mutations produce `unmapped` results without changing source.

`cwd` defaults to the project root and must resolve to a directory inside it.
`timeoutSeconds` defaults to 120 and must be a positive integer. Commands are
argument arrays, not shell strings. Invoke a shell explicitly if one is needed.
Commands inherit the environment. Python commands get an empty bytecode-cache
path and disabled bytecode writes to prevent stale imports. Other build and test
caches remain the user's responsibility.

Inspect manifests without execution:

```sh
uv run --project atlas atlas mutations --folder .
```

Run the configured commands for each independent mutation:

```sh
uv run --project atlas atlas mutations run --folder . --output mutation-results.jsonl
```

Progress logs stream to stderr during planning and execution. They show the
mapped/unmapped counts, mutation position and edit, target command, working
directory, timeout, command-log path, outcome, duration, and confirmed source
restoration. The final JSON summary stays on stdout. To save progress separately:

```sh
uv run --project atlas atlas mutations run --folder . --output results.jsonl 2>progress.log
```

`--output` resolves from the project root. Each result is written immediately as
one JSON object per line. Command output goes to separate files in
`<output>.logs/`. Choose a new output path for each run. Existing result files
are never overwritten. Parent output directories must already exist.

Each record includes the manifest ID, source path, rule ID, outcome, and command
results. Command results include target name, command, exit code, duration, and
log path. Outcomes are:

| Outcome | Meaning |
| --- | --- |
| `survived` | All matching commands returned zero. |
| `killed` | At least one matching command returned nonzero. |
| `timeout` | A command exceeded its timeout, with no kill or execution error. |
| `error` | Source validation or command execution failed, with no kill. |
| `unmapped` | No configured target matched the source path. |

A nonzero exit is not proof of a test assertion failure. Compilation errors,
empty test collections, and pre-existing failures can count as kills. The CLI
returns success when execution completes, even if mutations survive or records
contain errors. Inspect the result records for CI policy decisions.

Atlas verifies source hashes before editing and restores the exact original
bytes after each mutation. A restoration failure aborts execution. SIGINT and
SIGTERM restore the active mutation; SIGKILL, power loss, and machine failure
cannot guarantee restoration. Do not edit source or run another mutation process
in the same workspace during execution. Commands can change other files or
external services; Atlas does not roll those changes back. On POSIX systems,
Atlas stops each command's process group, including children, before restoration.
On other systems, it stops only the direct command process.

The repository configuration targets only `atlas/src/atlas/`. Dashboard and test
sources are not executed as mutants. They can still appear as `unmapped` records
because analysis and manifest inspection cover the entire project.
