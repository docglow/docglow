# MCP Server (AI Editor Integration)

Docglow includes a [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes your dbt project to AI editors like Claude Code, Cursor, and Copilot.

## Setup

Add to your editor's MCP config (e.g. `~/.claude.json` for Claude Code):

```json
{
  "mcpServers": {
    "docglow": {
      "command": "docglow",
      "args": ["mcp-server", "--project-dir", "/path/to/dbt/project"]
    }
  }
}
```

The server runs locally over stdio. No API keys or network access required.

## Available Tools

The MCP server exposes 9 tools:

| Tool | Description |
|------|-------------|
| `list_models` | List all models with metadata (name, description, materialization, folder) |
| `get_model` | Get full details for a model (columns, tests, SQL, dependencies) |
| `get_source` | Get full details for a source (columns, freshness status) |
| `get_lineage` | Get upstream/downstream dependencies for a model |
| `get_health` | Get the project health report (scores, coverage, violations) |
| `find_undocumented` | Find models and columns missing descriptions |
| `find_untested` | Find models and columns without tests |
| `search` | Full-text search across models, sources, and columns |
| `get_column_info` | Search for a column name across all models in the project |

## Use Cases

**With Claude Code or Cursor:**

- "What models depend on stg_orders?" — the AI uses `get_lineage` to trace dependencies
- "Which models need documentation?" — uses `find_undocumented` to list gaps
- "What does the customer_id column mean across the project?" — uses `get_column_info`
- "Help me write a description for dim_employee" — uses `get_model` to understand the model's SQL and columns

**In CI/CD:**

```bash
# Start the MCP server for automated documentation tasks
docglow mcp-server --project-dir /path/to/dbt
```

## Options

```bash
docglow mcp-server --project-dir /path/to/dbt    # Required: dbt project root
docglow mcp-server --target-dir /path/to/target   # Optional: custom target directory
```
