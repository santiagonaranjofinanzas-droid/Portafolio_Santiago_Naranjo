#AI Coding Guidelines - {{PROJECT_NAME}}

This repository uses automated AI tools to enhance development. Please follow these guidelines:

##Code Understanding
- **Graphify:** Refer to `graphify-out/GRAPH_REPORT.md` and query the graph using `graphify query "[question]"` before making architectural changes.
- **Serena:** Use symbol-level tools (references, implementations, declarations) for code searching and modifications instead of plain regex grep search.

##Code Quality
- **Preserve Documentation:** Do not delete or strip existing comments, docstrings, or annotations unless explicitly requested by the user.
- **Incremental Indexing:** Always run incremental updates (`graphify update .` and `serena project index`) after code modifications.

##Automated Hooks
- Do not bypass or disable lifecycle hooks in `.agents/hooks.json`.
- If a hook fails, check the log files in `.serena/logs/` or `.agents/last_run.txt`.
