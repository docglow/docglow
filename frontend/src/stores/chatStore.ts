import { create } from 'zustand'
import type { AiContext } from '../types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  referencedModels?: string[]
}

interface ChatState {
  open: boolean
  messages: ChatMessage[]
  streaming: boolean
  streamContent: string
  apiKey: string
  requestCount: number
  maxRequests: number
  error: string | null

  setOpen: (open: boolean) => void
  toggleOpen: () => void
  setApiKey: (key: string) => void
  clearMessages: () => void
  sendMessage: (content: string, aiContext: AiContext) => Promise<void>
}

// Key stored in sessionStorage (cleared when tab closes) to limit exposure
const STORAGE_KEY = 'dg-ai-key'
const MAX_REQUESTS = 20

function getStoredKey(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function storeKey(key: string) {
  try {
    if (key) {
      sessionStorage.setItem(STORAGE_KEY, key)
    } else {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // sessionStorage unavailable
  }
}

const SYSTEM_PROMPT = `You are an expert dbt analytics engineer assistant embedded in a documentation site. You help users understand their dbt project by answering questions about models, sources, lineage, tests, and data quality.

You have access to the full project metadata below. Use it to answer questions accurately.

Guidelines:
- Be concise and direct
- When referencing models, use their exact names in backticks
- When asked about dependencies, trace the lineage graph from the metadata
- When asked "what would break", list all downstream models that depend on the mentioned model
- When asked about data quality, reference test results and health scores
- If you're unsure about something, say so rather than guessing
- Use markdown formatting for readability`

function buildSystemPrompt(ctx: AiContext): string {
  return `${SYSTEM_PROMPT}

Project: ${ctx.project_name} (dbt ${ctx.dbt_version})
Stats: ${ctx.total_models} models, ${ctx.total_sources} sources, ${ctx.total_seeds} seeds
Health: ${ctx.health_summary.grade} (${ctx.health_summary.overall_score}/100), ${(ctx.health_summary.documentation_coverage * 100).toFixed(0)}% documented, ${(ctx.health_summary.test_coverage * 100).toFixed(0)}% tested

Models:
${JSON.stringify(ctx.models, null, 0)}

Sources:
${JSON.stringify(ctx.sources, null, 0)}`
}

function extractModelRefs(text: string, modelNames: string[]): string[] {
  const found: string[] = []
  for (const name of modelNames) {
    if (text.includes(name)) {
      found.push(name)
    }
  }
  return found
}

export const useChatStore = create<ChatState>((set, get) => ({
  open: false,
  messages: [],
  streaming: false,
  streamContent: '',
  apiKey: getStoredKey(),
  requestCount: 0,
  maxRequests: MAX_REQUESTS,
  error: null,

  setOpen: (open) => set({ open }),
  toggleOpen: () => set(s => ({ open: !s.open })),

  setApiKey: (key) => {
    storeKey(key)
    set({ apiKey: key, error: null })
  },

  clearMessages: () => set({ messages: [], requestCount: 0, error: null }),

  sendMessage: async (content, aiContext) => {
    const { apiKey, messages, requestCount, maxRequests } = get()

    if (!apiKey) {
      set({ error: 'Please set your Anthropic API key to use AI chat.' })
      return
    }

    if (requestCount >= maxRequests) {
      set({ error: `Rate limit reached (${maxRequests} requests per session). Clear chat to reset.` })
      return
    }

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    set({
      messages: [...messages, userMsg],
      streaming: true,
      streamContent: '',
      error: null,
    })

    const systemPrompt = buildSystemPrompt(aiContext)
    const apiMessages = [...messages, userMsg].map(m => ({
      role: m.role,
      content: m.content,
    }))

    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 2048,
          system: systemPrompt,
          messages: apiMessages,
          stream: true,
        }),
      })

      if (!response.ok) {
        const errText = await response.text()
        let errMsg = `API error: ${response.status}`
        try {
          const errJson = JSON.parse(errText)
          errMsg = errJson.error?.message ?? errMsg
        } catch {
          // use default error message
        }
        set({ streaming: false, error: errMsg })
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        set({ streaming: false, error: 'Failed to read response stream' })
        return
      }

      const decoder = new TextDecoder()
      let fullContent = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const event = JSON.parse(data)
            if (event.type === 'content_block_delta' && event.delta?.text) {
              fullContent += event.delta.text
              set({ streamContent: fullContent })
            }
          } catch {
            // skip malformed events
          }
        }
      }

      const modelNames = aiContext.models.map(m => m.name)
      const refs = extractModelRefs(fullContent, modelNames)

      const assistantMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: fullContent,
        timestamp: Date.now(),
        referencedModels: refs.length > 0 ? refs : undefined,
      }

      set(s => ({
        messages: [...s.messages, assistantMsg],
        streaming: false,
        streamContent: '',
        requestCount: s.requestCount + 1,
      }))
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send message'
      set({ streaming: false, error: msg })
    }
  },
}))
