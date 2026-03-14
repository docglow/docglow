Create a Linear issue for the Docglow project.

Arguments: $ARGUMENTS

The arguments should contain the issue title and optionally a description, priority, status, and labels.

## Instructions

Use Python (urllib.request) to call the Linear GraphQL API — do NOT use curl, as shell quoting breaks the auth header.

**API Details:**
- Endpoint: `https://api.linear.app/graphql`
- Auth header: `Authorization: <value of LINEAR_API_KEY env var>`
- Team ID: `0489f9e3-e966-4210-a253-2e4e61dbab9b` (Docglow)

**Workflow States:**
| State | ID | Type |
|-------|----|------|
| Backlog | `abbbb27c-86c7-40f4-a8fb-cb944ee37ad6` | backlog |
| Todo | `aacc072e-58e2-4abb-98e5-b8acd0aea39b` | unstarted |
| In Progress | `440e4e01-bb8f-4c92-b59f-b73b8578c636` | started |
| In Review | `f204a915-36ae-4826-beaa-b9ad720048f1` | started |
| Done | `5823d46d-1bab-483c-a688-1a810b75344c` | completed |
| Canceled | `63cf8544-7c71-459c-8f6a-39190b29b87a` | canceled |
| Duplicate | `7f516608-956f-4e6c-b5f6-ab5dff5cfbd8` | canceled |

**Labels:**
| Label | ID |
|-------|----|
| Bug | `bb67a124-9f9b-4652-8a06-d23c96673d8b` |
| Feature | `6e98a407-d731-4900-b18f-d8094c538784` |
| Improvement | `4303eabb-00d6-49c0-b287-8f0fb7ac28cd` |

**Priority values:** 0 = No priority, 1 = Urgent, 2 = High, 3 = Medium, 4 = Low

## Behavior

1. Parse the arguments to extract: title, description, priority, state, and labels
2. If only a title-like string is provided, use it as the title with no description
3. If the user provides context about what the issue is for, craft a clear markdown description
4. Default state: Backlog (unless specified)
5. Default priority: 0 (unless specified)
6. Build the `issueCreate` mutation with the appropriate input fields
7. Execute via Python urllib.request (NOT curl)
8. Report back the issue identifier (e.g. DOC-6), title, and URL

## Example Python pattern

```python
import os, json, urllib.request
key = os.environ['LINEAR_API_KEY']
query = 'mutation { issueCreate(input: { title: "...", teamId: "0489f9e3-e966-4210-a253-2e4e61dbab9b" }) { success issue { id identifier title url } } }'
data = json.dumps({'query': query}).encode()
req = urllib.request.Request('https://api.linear.app/graphql', data=data, headers={'Content-Type': 'application/json', 'Authorization': key})
resp = urllib.request.urlopen(req)
result = json.loads(resp.read().decode())
```

## Querying issues

If the user asks to list, search, or check issues instead of creating, use the appropriate query:

```graphql
{ issues(filter: { team: { id: { eq: "0489f9e3-e966-4210-a253-2e4e61dbab9b" } } }) { nodes { identifier title state { name } priority url } } }
```
