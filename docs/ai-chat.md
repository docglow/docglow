# AI Chat (Bring Your Own Key)

Docglow includes a built-in AI chat panel powered by Claude. Ask natural language questions about your dbt project and get answers grounded in your actual metadata — models, columns, lineage, tests, and health scores.

## Enable AI Chat

```bash
# Pass your key as a flag
docglow generate --ai --ai-key sk-ant-...

# Or set the environment variable
export ANTHROPIC_API_KEY=sk-ant-...
docglow generate --ai

# Or enable in docglow.yml
# ai:
#   enabled: true
```

Open the chat panel with ++ctrl+j++ (or click the chat icon in the header), enter your Anthropic API key, and start asking questions.

## Example Questions

| Question | What it does |
|----------|-------------|
| *What models depend on the orders source?* | Traces the lineage graph to find all downstream consumers |
| *Which columns might contain PII?* | Scans column names and descriptions for personally identifiable information |
| *What would break if I changed stg_customers?* | Lists all downstream models that depend on `stg_customers` |
| *Show me all models related to revenue* | Searches model names, descriptions, and tags |
| *Which models have the most failing tests?* | Cross-references test results with model metadata |
| *What's the overall health of this project?* | Summarizes the health score breakdown across all six dimensions |
| *Explain what dim_employee does* | Describes the model using its SQL, columns, and dependencies |
| *What's the difference between stg_orders and fct_orders?* | Compares two models side-by-side |

## How It Works

When you generate with `--ai`, Docglow builds a compact project context (model names, descriptions, columns, lineage, test status, health scores) and embeds it in the site. The chat panel sends this context as a system prompt to the Anthropic API along with your question. Responses stream back in real-time with clickable model references.

## Security

Your API key is **never embedded** in the generated site. It's stored in your browser's localStorage when you enter it in the chat panel, and sent directly to the Anthropic API from your browser. You can safely deploy AI-enabled sites — they contain the project context but not your key.

## Limits

- 20 requests per session (clear chat to reset)
- Uses Claude Sonnet 4 with streaming
- Max 2,048 tokens per response
