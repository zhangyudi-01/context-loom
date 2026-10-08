# Run a testing pilot without touching the original module

The `loom-test-points` Skill is the conversational entry point. The Python runtime is installed
separately; installing Skill instructions does not install the CLI.

```powershell
npx skills@latest add zhangyudi-01/context-loom --skill loom-test-points --agent codex --global --yes
python -m pip install -e D:\pythonProject\context-loom
```

In Codex, invoke `$loom-test-points` with an existing preanalyzed module path and selected RSUs,
or run the commands yourself:

New preanalysis lives under `MODULE_DIR/preanalysis/` and has a `preanalysis/v1` manifest.
Finish the [requirement-preanalysis Skill](quickstart-testing-preanalysis.md) and its full
validation first. Setup resolves the manifest's actual artifact and fixed-resource paths;
it also checks selected RSU wording and the readiness of direct Q/FC/DC dependencies.
Legacy flat inputs without a manifest still require `global/project-context.md`.

```powershell
context-loom setup-testing --module <absolute-module-dir> --output <new-directory-outside-source-project> --rsu RSU-001 RSU-002
context-loom doctor <new-directory>      # no model calls
context-loom compile <new-directory>     # no model calls
context-loom run <new-directory>         # makes paid Codex CLI model calls
context-loom status <new-directory>
```

The pilot generates `.context-loom/module-test-points.md` and `.context-loom/trace.json` in the
new directory. It uses the real global context, literal module requirement, module context,
selected RSU quotes and referenced context cards/data closures as read-only input. Only the
selected RSUs are covered. Review the result before using it in a production testing pipeline;
the pilot does not reproduce the original project's entire test-point validation workflow.

If `doctor` fails on the Codex CLI, run `doctor <new-directory> --offline` to validate the
inputs without checking the agent host. The CLI currently needs a Codex version that supports
`codex exec fork`; check authentication separately before a paid run. Never commit pilot
configuration containing absolute private project paths to a public repository.
