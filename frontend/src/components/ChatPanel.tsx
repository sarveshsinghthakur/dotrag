import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft, Send, Loader2, FileText, Image as ImageIcon,
  ExternalLink, Paperclip, BookOpen, Zap, Library, Lock,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import { api } from '../services/api';
import type { ChatMessage, Citation, Document, UploadOptions } from '../types';

interface ChatPanelProps {
  selectedDocIds: string[];
  onBack: () => void;
  documents: Document[];
  onUpload: (file: File, options?: UploadOptions) => Promise<unknown>;
  onRefresh: () => void;
  conversationId?: string;
  onConversationIdChange?: (id: string) => void;
}

// ─── Markdown renderer ────────────────────────────────────────────────────────
function MessageContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="text-base font-bold font-mono mt-3 mb-1 text-white">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-bold font-mono mt-3 mb-1 text-white">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1 text-white/90">{children}</h3>,
        p:  ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-white/90">{children}</p>,
        ul: ({ children }) => <ul className="my-2 space-y-0.5 pl-4">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 space-y-0.5 pl-4 list-decimal">{children}</ol>,
        li: ({ children }) => (
          <li className="text-white/90 before:content-['·'] before:mr-2 before:text-dot-dim">{children}</li>
        ),
        code: ({ inline, children, ...props }: any) =>
          inline ? (
            <code className="px-1.5 py-0.5 bg-white/10 text-green-300 font-mono text-xs rounded" {...props}>
              {children}
            </code>
          ) : (
            <code className="block p-3 my-2 bg-black/50 border border-white/10 font-mono text-xs text-green-300 overflow-x-auto" {...props}>
              {children}
            </code>
          ),
        pre: ({ children }) => <pre className="overflow-x-auto">{children}</pre>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-dot-dim/50 pl-3 my-2 italic text-dot-dim">{children}</blockquote>
        ),
        strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
        em:     ({ children }) => <em className="italic text-white/80">{children}</em>,
        hr: () => <hr className="my-3 border-dot-dim/30" />,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer"
             className="text-white underline underline-offset-2 hover:text-dot-dim transition-colors">
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div className="my-2 overflow-x-auto">
            <table className="text-xs border-collapse w-full">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-dot-dim/30 px-2 py-1 font-mono font-bold text-left bg-white/5">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border border-dot-dim/30 px-2 py-1">{children}</td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ─── Status indicator ─────────────────────────────────────────────────────────
function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    'analyzing query':          'Analyzing…',
    'searching documents':      'Searching…',
    'generating response':      'Generating…',
    'vector search unavailable': 'No vector DB',
    'no documents in scope':    'No docs in scope',
    'complete':                 'Done',
  };
  const label = map[status] ?? status;
  if (!label || status === 'complete') return null;

  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-mono text-dot-dim border border-dot-dim/20 bg-white/3">
      <span className="w-1.5 h-1.5 rounded-full bg-white/60 status-pulse inline-block" />
      {label}
    </span>
  );
}

// ─── File icon ────────────────────────────────────────────────────────────────
function DocFileIcon({ fileType }: { fileType?: string }) {
  if (fileType === 'image') return <ImageIcon className="w-3 h-3 text-dot-dim" />;
  return <FileText className="w-3 h-3 text-dot-dim" />;
}

// ─── Scope badge ──────────────────────────────────────────────────────────────
function ScopeBadge({ scope }: { scope: 'library' | 'chat' }) {
  return scope === 'library' ? (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-mono text-emerald-400/70 border border-emerald-400/20 bg-emerald-400/5">
      <Library className="w-2.5 h-2.5" />lib
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-mono text-yellow-400/70 border border-yellow-400/20 bg-yellow-400/5">
      <Lock className="w-2.5 h-2.5" />chat
    </span>
  );
}

// ─── Document context panel ───────────────────────────────────────────────────
function ContextPanel({
  docs,
  conversationId,
}: {
  docs: Document[];
  conversationId?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const libraryDocs = docs.filter((d) => d.scope === 'library' && d.status === 'ready');
  const chatDocs    = docs.filter((d) => d.scope === 'chat' && d.status === 'ready' && d.conversation_id === conversationId);
  const total = libraryDocs.length + chatDocs.length;

  if (total === 0) return null;

  return (
    <div className="border-b border-white/8 bg-white/2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-mono text-dot-dim hover:text-white transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <BookOpen className="w-3 h-3" />
          {total} doc{total !== 1 ? 's' : ''} in context
          {libraryDocs.length > 0 && (
            <span className="text-emerald-400/60 ml-1">{libraryDocs.length} lib</span>
          )}
          {chatDocs.length > 0 && (
            <span className="text-yellow-400/60 ml-1">{chatDocs.length} chat</span>
          )}
        </span>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {expanded && (
        <div className="px-4 pb-2 space-y-1">
          {libraryDocs.map((d) => (
            <div key={d.id} className="flex items-center gap-2">
              <DocFileIcon fileType={d.file_type} />
              <span className="text-xs text-dot-dim truncate flex-1">{d.filename}</span>
              <ScopeBadge scope="library" />
            </div>
          ))}
          {chatDocs.map((d) => (
            <div key={d.id} className="flex items-center gap-2">
              <DocFileIcon fileType={d.file_type} />
              <span className="text-xs text-dot-dim truncate flex-1">{d.filename}</span>
              <ScopeBadge scope="chat" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function ChatPanel({
  selectedDocIds,
  onBack,
  documents,
  onUpload,
  onRefresh,
  conversationId: initialConvId,
  onConversationIdChange,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(initialConvId);
  const [status, setStatus] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef       = useRef<HTMLTextAreaElement>(null);
  const fileInputRef   = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Resolve doc IDs for this session — backend handles scope, but we
  // pass empty array to let the backend auto-resolve via conversation context.
  const resolvedDocIds = selectedDocIds.length > 0 ? selectedDocIds : [];

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      await onUpload(file, {
        scope: 'chat',
        conversation_id: conversationId,
      });
      // Poll for processing completion
      setTimeout(() => onRefresh(), 1500);
      setTimeout(() => onRefresh(), 4000);
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const query = input.trim();
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStatus('analyzing query');

    const assistantId = 'assistant-' + Date.now();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', timestamp: new Date().toISOString() },
    ]);

    try {
      let fullResponse = '';
      let citations: Citation[] = [];

      // Pass conversationId so the backend can resolve scope-aware doc IDs
      const stream = api.chatStream(query, conversationId, resolvedDocIds);

      for await (const event of stream) {
        switch (event.type) {
          case 'status':
            setStatus(event.content as string);
            break;
          case 'chunk':
            fullResponse += event.content;
            setMessages((prev) =>
              prev.map((m) => m.id === assistantId ? { ...m, content: fullResponse } : m)
            );
            break;
          case 'citations':
            citations = event.content as Citation[];
            setMessages((prev) =>
              prev.map((m) => m.id === assistantId ? { ...m, citations } : m)
            );
            break;
          case 'conversation_id': {
            const cid = event.content as string;
            setConversationId(cid);
            onConversationIdChange?.(cid);
            break;
          }
          case 'done':
            break;
        }
      }
    } catch (err) {
      console.error('Stream error:', err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: 'An error occurred while processing your request. Please try again.' }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setStatus('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const SUGGESTIONS = [
    'Summarize this document',
    'What are the key findings?',
    'List the main topics covered',
    'Extract important dates or numbers',
  ];

  return (
    <div className="flex flex-col h-full bg-dot-black">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-dot-dark/60 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded hover:bg-white/10 transition-colors"
            aria-label="Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-white/60" />
              <span className="font-mono text-sm font-bold tracking-wider">Research Chat</span>
            </div>
            <p className="text-xs text-dot-dim mt-0.5">
              {conversationId ? 'Active session' : 'New session'}
            </p>
          </div>
        </div>
        {status && <StatusPill status={status} />}
      </div>

      {/* ── Context panel ── */}
      <ContextPanel docs={documents} conversationId={conversationId} />

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-6 py-16">
            <div className="w-16 h-16 border border-white/10 flex items-center justify-center bg-white/3">
              <BookOpen className="w-7 h-7 text-dot-dim" />
            </div>
            <div className="space-y-2 max-w-sm">
              <p className="font-mono text-sm font-medium">Ask anything about your documents</p>
              <p className="text-xs text-dot-dim leading-relaxed">
                Library documents are always available. Files uploaded here are scoped to this chat.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-sm">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="px-3 py-1.5 text-xs font-mono border border-white/10 text-dot-dim
                             hover:border-white/30 hover:text-white transition-colors text-left"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message-enter flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-3xl w-full ${msg.role === 'user' ? 'flex flex-col items-end' : ''}`}>
              {/* Role label */}
              <div className="flex items-center gap-2 mb-1.5">
                {msg.role === 'assistant' && (
                  <div className="w-4 h-4 bg-white rounded-full flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-black rounded-full" />
                  </div>
                )}
                <span className="text-xs font-mono text-dot-dim tracking-wider">
                  {msg.role === 'user' ? 'YOU' : 'DOTRAG'}
                </span>
              </div>

              {/* Bubble */}
              <div
                className={`px-4 py-3 text-sm ${
                  msg.role === 'user'
                    ? 'bg-white/10 border border-white/15 text-white ml-12'
                    : 'bg-dot-dark border border-white/8 text-white/90 mr-12'
                }`}
              >
                {msg.role === 'user' ? (
                  <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                ) : msg.content ? (
                  <MessageContent content={msg.content} />
                ) : (
                  <div className="flex items-center gap-1 py-1">
                    <span className="w-1.5 h-1.5 bg-dot-dim rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 bg-dot-dim rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 bg-dot-dim rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                )}

                {/* Blinking cursor while streaming */}
                {isStreaming &&
                  msg.role === 'assistant' &&
                  msg.id === messages[messages.length - 1]?.id &&
                  msg.content && (
                    <span className="cursor-blink ml-0.5 text-dot-dim" />
                  )}
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2.5 mr-12 space-y-1">
                  <p className="text-xs font-mono text-dot-dim/50 tracking-widest mb-1">SOURCES</p>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.citations.map((cite, idx) => (
                      <div
                        key={idx}
                        title={cite.text_snippet}
                        className="flex items-center gap-1.5 px-2 py-1 border border-white/10
                                   bg-white/3 hover:bg-white/6 hover:border-white/20 transition-all cursor-default group"
                      >
                        <span className="font-mono text-xs text-dot-dim/50">
                          [{cite.citation_index ?? idx + 1}]
                        </span>
                        <FileText className="w-3 h-3 text-dot-dim" />
                        <span className="text-xs text-dot-dim group-hover:text-white transition-colors max-w-[140px] truncate">
                          {cite.document_name}
                        </span>
                        <span className="text-xs text-dot-dim/40">p.{cite.page_number}</span>
                        <ExternalLink className="w-2.5 h-2.5 text-dot-dim/30 group-hover:text-dot-dim transition-colors" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input ── */}
      <div className="border-t border-white/10 p-4 bg-dot-dark/60 backdrop-blur-sm">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.tif,.webp"
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || isStreaming}
            title="Upload file to this chat"
            className="p-3 border border-white/10 text-dot-dim hover:text-white
                       hover:border-white/30 transition-all disabled:opacity-30
                       disabled:cursor-not-allowed flex-shrink-0 group relative"
          >
            {isUploading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Paperclip className="w-4 h-4" />
            )}
            <span className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap
                             hidden group-hover:block text-xs font-mono text-dot-dim
                             bg-dot-dark border border-white/10 px-2 py-0.5 pointer-events-none">
              Upload to this chat
            </span>
          </button>

          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
              rows={1}
              className="w-full bg-black/40 border border-white/10 px-4 py-3
                         text-sm font-mono resize-none overflow-hidden
                         focus:outline-none focus:border-white/30 transition-colors
                         placeholder:text-dot-dim/30 max-h-[120px]"
              disabled={isStreaming}
            />
          </div>

          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-3 bg-white text-black hover:bg-gray-100 transition-colors
                       disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>

        <p className="text-xs text-dot-dim/25 font-mono mt-2 text-center">
          AI responses may contain errors · verify with source documents
        </p>
      </div>
    </div>
  );
}
