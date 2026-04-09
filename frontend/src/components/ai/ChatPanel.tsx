import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import DOMPurify from 'dompurify'
import { useChatStore } from '../../stores/chatStore'
import { useProjectStore } from '../../stores/projectStore'
import type { ChatMessage } from '../../stores/chatStore'

const STARTER_QUESTIONS = [
  'What models depend on the orders source?',
  'Which columns might contain PII?',
  'What would break if I changed stg_customers?',
  'Show me all models related to revenue',
  'Which models have the most failing tests?',
  'What\'s the overall health of this project?',
]

function MarkdownContent({ content }: { content: string }) {
  // Simple markdown: bold, code, backticks, newlines
  const rawHtml = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-[var(--bg-surface)] text-xs font-mono">$1</code>')
    .replace(/\n/g, '<br/>')

  const html = DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: ['strong', 'code', 'br'],
    ALLOWED_ATTR: ['class'],
  })

  return <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: html }} />
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const navigate = useNavigate()
  const { data } = useProjectStore()
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-lg px-3 py-2 ${
        isUser
          ? 'bg-primary text-white'
          : 'bg-[var(--bg-surface)] border border-[var(--border)]'
      }`}>
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <MarkdownContent content={message.content} />
        )}

        {message.referencedModels && message.referencedModels.length > 0 && data && (
          <div className="mt-2 pt-2 border-t border-[var(--border)] flex flex-wrap gap-1">
            {message.referencedModels.map(name => {
              const model = Object.values(data.models).find(m => m.name === name)
              if (!model) return null
              return (
                <button
                  key={name}
                  onClick={() => navigate(`/model/${encodeURIComponent(model.unique_id)}`)}
                  className="px-2 py-0.5 text-xs rounded bg-primary/10 text-primary
                             hover:bg-primary/20 transition-colors cursor-pointer"
                >
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function ApiKeySetup() {
  const [key, setKey] = useState('')
  const { setApiKey } = useChatStore()

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        <div className="text-4xl mb-3">🤖</div>
        <h3 className="font-semibold mb-2">AI Chat Setup</h3>
        <p className="text-sm text-[var(--text-muted)] mb-4">
          Enter your Anthropic API key to enable AI-powered chat.
          Your key is stored in session storage and cleared when the tab closes.
        </p>
        <p className="text-xs text-[var(--text-muted)] mb-4">
          Note: When using AI chat, your project metadata (model names, descriptions,
          columns, lineage, health scores) is sent to Anthropic's API.
        </p>
        <input
          type="password"
          value={key}
          onChange={e => setKey(e.target.value)}
          placeholder="sk-ant-..."
          className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded-lg
                     bg-[var(--bg)] outline-none focus:border-primary mb-2"
        />
        <button
          onClick={() => setApiKey(key)}
          disabled={!key.startsWith('sk-')}
          className="w-full px-4 py-2 text-sm font-medium rounded-lg
                     bg-primary text-white hover:bg-primary/90
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors cursor-pointer"
        >
          Save Key
        </button>
        <p className="text-xs text-[var(--text-muted)] mt-2">
          Get a key at{' '}
          <span className="text-primary">console.anthropic.com</span>
        </p>
      </div>
    </div>
  )
}

export function ChatPanel() {
  const { data } = useProjectStore()
  const {
    open, setOpen, messages, streaming, streamContent,
    apiKey, requestCount, maxRequests, error,
    sendMessage, clearMessages,
  } = useChatStore()

  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamContent])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // Keyboard shortcut: Ctrl/Cmd + J to toggle
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault()
        useChatStore.getState().toggleOpen()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  if (!open) return null

  const aiContext = data?.ai_context

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || streaming || !aiContext) return
    setInput('')
    sendMessage(trimmed, aiContext)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed right-0 top-14 bottom-0 w-96 border-l border-[var(--border)]
                    bg-[var(--bg)] flex flex-col z-50 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">AI Chat</span>
          <span className="text-xs text-[var(--text-muted)]">
            {requestCount}/{maxRequests}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="p-1.5 rounded hover:bg-[var(--bg-surface)] transition-colors cursor-pointer"
              title="Clear chat"
            >
              <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 rounded hover:bg-[var(--bg-surface)] transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      {!apiKey ? (
        <ApiKeySetup />
      ) : !aiContext ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-[var(--text-muted)] text-center">
            AI chat requires generating the site with the <code className="px-1 py-0.5 rounded bg-[var(--bg-surface)] text-xs">--ai</code> flag.
          </p>
        </div>
      ) : (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && !streaming && (
              <div className="space-y-2">
                <p className="text-sm text-[var(--text-muted)] mb-3">
                  Ask anything about your dbt project:
                </p>
                {STARTER_QUESTIONS.map(q => (
                  <button
                    key={q}
                    onClick={() => {
                      setInput('')
                      sendMessage(q, aiContext)
                    }}
                    className="w-full text-left px-3 py-2 text-xs rounded-lg
                               border border-[var(--border)] hover:border-primary/30
                               hover:bg-[var(--bg-surface)] transition-colors cursor-pointer"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {streaming && streamContent && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg px-3 py-2 bg-[var(--bg-surface)] border border-[var(--border)]">
                  <MarkdownContent content={streamContent} />
                  <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5" />
                </div>
              </div>
            )}

            {streaming && !streamContent && (
              <div className="flex justify-start">
                <div className="rounded-lg px-3 py-2 bg-[var(--bg-surface)] border border-[var(--border)]">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="px-3 py-2 rounded-lg bg-danger/10 text-danger text-xs">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-[var(--border)] shrink-0">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your dbt project..."
                disabled={streaming}
                className="flex-1 px-3 py-2 text-sm border border-[var(--border)] rounded-lg
                           bg-[var(--bg)] outline-none focus:border-primary
                           disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || streaming}
                className="px-3 py-2 rounded-lg bg-primary text-white text-sm font-medium
                           hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
            <div className="flex justify-between mt-1.5 text-[10px] text-[var(--text-muted)]">
              <span>{navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+J to toggle</span>
              <span>Enter to send</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
