Rebuild the frontend, regenerate the docglow site from the point_analytics dbt project, and serve it locally.

Steps:
1. Build the frontend: `cd frontend && npm run build && cd ..`
2. Regenerate the site: `uv run docglow generate --project-dir /home/josh/Documents/projects/personal/analytics/dbt/point_analytics --output-dir /tmp/docglow-point-analytics --verbose`
3. Kill any existing server on port 8765
4. Start the server: `uv run docglow serve --dir /tmp/docglow-point-analytics --port 8765 --no-open`
5. Report the URL: http://localhost:8765

If any step fails, stop and report the error.
