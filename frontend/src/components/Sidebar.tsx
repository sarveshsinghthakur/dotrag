import { useState } from 'react';
import {
  PanelLeftClose, PanelLeftOpen, FileText, Image, Trash2, RefreshCw, Plus,
  MessageSquare, Layers, Loader2, Library, Lock,
} from 'lucide-react';
import type { Document, DocumentScope, UploadOptions } from '../types';
import UploadZone from './UploadZone';

interface SidebarProps {
  documents: Document[];
  isOpen: boolean;
  onToggle: () => void;
  onSelectDoc: (doc: Document) => void;
  onOpenChat: (docIds?: string[]) => void;
  onDelete: (id: string) => void;
  onUpload: (file: File, options?: UploadOptions) => Promise<unknown>;
  onRefresh: () => void;
  selectedDocId?: string;
  loading: boolean;
  /** Active conversation id — if set, upload defaults to CHAT scope */
  activeConversationId?: string;
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusDot({ status }: { status: Document['status'] }) {
  const classes: Record<string, string> = {
    ready: 'bg-emerald-400',
    processing: 'bg-yellow-400 animate-pulse',
    indexing: 'bg-yellow-400 animate-pulse',
    uploading: 'bg-blue-400 animate-pulse',
    error: 'bg-red-400',
  };
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${classes[status] ?? 'bg-gray-500'}`} />
  );
}

function StatusText({ status }: { status: Document['status'] }) {
  const map: Record<string, { label: string; cls: string }> = {
    ready:      { label: 'Ready',      cls: 'text-emerald-400' },
    processing: { label: 'Processing', cls: 'text-yellow-400'  },
    indexing:   { label: 'Indexing',   cls: 'text-yellow-400'  },
    uploading:  { label: 'Uploading',  cls: 'text-blue-400'    },
    error:      { label: 'Error',      cls: 'text-red-400'     },
  };
  const { label, cls } = map[status] ?? { label: status, cls: 'text-dot-dim' };
  return <span className={`text-xs font-mono ${cls}`}>{label}</span>;
}

function FileIcon({ fileType }: { fileType: string }) {
  if (fileType === 'image') return <Image className="w-3.5 h-3.5 text-dot-dim flex-shrink-0" />;
  return <FileText className="w-3.5 h-3.5 text-dot-dim flex-shrink-0" />;
}

// ─── Document row ─────────────────────────────────────────────────────────────
function DocRow({
  doc,
  isSelected,
  isDeleting,
  onSelect,
  onDelete,
}: {
  doc: Document;
  index?: number;
  isSelected: boolean;
  isDeleting: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`
        group relative p-2.5 cursor-pointer transition-all duration-100
        border rounded-sm
        ${isSelected
          ? 'border-white/25 bg-white/6'
          : 'border-transparent hover:border-white/10 hover:bg-white/3'}
      `}
    >
      <div className="flex items-start gap-2">
        <div className="mt-0.5">
          <FileIcon fileType={doc.file_type ?? 'pdf'} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium truncate leading-snug">{doc.filename}</p>
          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
            <StatusDot status={doc.status} />
            <StatusText status={doc.status} />
            <span className="text-dot-dim/30 text-xs">·</span>
            <span className="text-xs text-dot-dim/50">{formatSize(doc.file_size)}</span>
            {doc.page_count > 0 && (
              <>
                <span className="text-dot-dim/30 text-xs">·</span>
                <span className="text-xs text-dot-dim/50">{doc.page_count}p</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-1
                     hover:bg-red-500/10 rounded transition-all disabled:opacity-50"
          title="Delete document"
        >
          {isDeleting
            ? <Loader2 className="w-3 h-3 text-red-400 animate-spin" />
            : <Trash2 className="w-3 h-3 text-dot-dim hover:text-red-400 transition-colors" />}
        </button>
      </div>
    </div>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────
function SectionHeader({
  icon: Icon,
  label,
  count,
}: {
  icon: React.FC<{ className?: string }>;
  label: string;
  count: number;
}) {
  return (
    <div className="flex items-center justify-between mb-1.5 px-0.5">
      <div className="flex items-center gap-1.5">
        <Icon className="w-3 h-3 text-dot-dim/60" />
        <span className="text-xs font-mono text-dot-dim/60 tracking-widest uppercase">{label}</span>
      </div>
      <span className="text-xs font-mono text-dot-dim/30">{count}</span>
    </div>
  );
}

// ─── Main Sidebar ─────────────────────────────────────────────────────────────
export default function Sidebar({
  documents,
  isOpen,
  onToggle,
  onSelectDoc,
  onOpenChat,
  onDelete,
  onUpload,
  onRefresh,
  selectedDocId,
  loading,
  activeConversationId,
}: SidebarProps) {
  const [showUpload, setShowUpload] = useState(false);
  const [uploadScope, setUploadScope] = useState<DocumentScope>('library');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const libraryDocs = documents.filter((d) => d.scope === 'library');
  const chatDocs = documents.filter((d) => d.scope === 'chat');
  const readyCount = documents.filter((d) => d.status === 'ready').length;

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeletingId(id);
    await onDelete(id);
    setDeletingId(null);
  };

  const handleUpload = async (file: File) => {
    return onUpload(file, {
      scope: uploadScope,
      conversation_id: uploadScope === 'chat' ? activeConversationId : undefined,
    });
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/60 z-30 md:hidden" onClick={onToggle} />
      )}

      {/* Mobile toggle */}
      <button
        onClick={onToggle}
        className="fixed top-4 left-4 z-50 p-2 bg-dot-dark border border-white/10
                   hover:border-white/30 transition-colors md:hidden"
      >
        {isOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
      </button>

      {/* Sidebar panel */}
      <aside
        className={`
          fixed md:relative z-40 h-full flex flex-col
          w-72 bg-dot-dark border-r border-white/8
          transition-all duration-200 ease-in-out
          ${isOpen
            ? 'translate-x-0'
            : '-translate-x-full md:-translate-x-full md:w-0 md:min-w-0 md:overflow-hidden md:border-0'}
        `}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/8">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 bg-white rounded-full" />
            <span className="font-mono text-sm font-bold tracking-widest">DOTRAG</span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={onRefresh} title="Refresh" className="p-1.5 rounded hover:bg-white/10 transition-colors">
              <RefreshCw className="w-3.5 h-3.5 text-dot-dim" />
            </button>
            <button onClick={onToggle} title="Collapse" className="p-1.5 rounded hover:bg-white/10 transition-colors hidden md:flex">
              <PanelLeftClose className="w-3.5 h-3.5 text-dot-dim" />
            </button>
          </div>
        </div>

        {/* ── Research session button ── */}
        <div className="px-3 pt-3 pb-2">
          <button
            onClick={() => {
              const readyDocs = documents.filter((d) => d.status === 'ready');
              onOpenChat(readyDocs.map((d) => d.id));
            }}
            disabled={readyCount === 0}
            className="w-full flex items-center justify-center gap-2 py-2.5
                       bg-white text-black text-xs font-mono font-bold
                       hover:bg-gray-100 transition-colors tracking-wider
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            NEW CHAT
            {readyCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 bg-black/20 text-xs rounded-full">{readyCount}</span>
            )}
          </button>
        </div>

        {/* ── Upload section ── */}
        <div className="px-3 pb-2 border-b border-white/8">
          {showUpload ? (
            <div className="space-y-2">
              {/* Scope selector */}
              <div className="flex gap-1">
                {(['library', 'chat'] as DocumentScope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setUploadScope(s)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-mono
                      border transition-all
                      ${uploadScope === s
                        ? 'border-white/40 bg-white/10 text-white'
                        : 'border-white/10 text-dot-dim hover:border-white/20'}`}
                  >
                    {s === 'library' ? <Library className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                    {s === 'library' ? 'Library' : 'This Chat'}
                  </button>
                ))}
              </div>
              {uploadScope === 'chat' && !activeConversationId && (
                <p className="text-xs text-yellow-400/80 font-mono px-0.5">
                  Open a chat first to upload chat-scoped files.
                </p>
              )}
              <UploadZone
                onUpload={handleUpload}
                compact
                disabled={uploadScope === 'chat' && !activeConversationId}
              />
              <button
                onClick={() => setShowUpload(false)}
                className="w-full text-xs text-dot-dim hover:text-white transition-colors py-1 font-mono"
              >
                ✕ Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowUpload(true)}
              className="w-full flex items-center justify-center gap-2 py-2
                         border border-white/10 text-xs font-mono text-dot-dim
                         hover:border-white/30 hover:text-white transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              Upload File
            </button>
          )}
        </div>

        {/* ── Document list ── */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="py-10 flex flex-col items-center gap-2 text-dot-dim">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-xs font-mono">Loading…</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="py-10 flex flex-col items-center gap-2 text-dot-dim/40">
              <Layers className="w-6 h-6" />
              <span className="text-xs font-mono">No documents yet</span>
              <span className="text-xs font-mono text-center px-4">Upload a PDF or image to get started</span>
            </div>
          ) : (
            <div className="px-3 py-3 space-y-4">
              {/* ── Library section ── */}
              {libraryDocs.length > 0 && (
                <div>
                  <SectionHeader icon={Library} label="Library" count={libraryDocs.length} />
                  <div className="space-y-0.5">
                    {libraryDocs.map((doc) => (
                      <DocRow
                        key={doc.id}
                        doc={doc}
                        isSelected={selectedDocId === doc.id}
                        isDeleting={deletingId === doc.id}
                        onSelect={() => onSelectDoc(doc)}
                        onDelete={(e) => handleDelete(e, doc.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* ── Chat-scoped section ── */}
              {chatDocs.length > 0 && (
                <div>
                  <SectionHeader icon={Lock} label="Chat Only" count={chatDocs.length} />
                  <div className="space-y-0.5">
                    {chatDocs.map((doc) => (
                      <DocRow
                        key={doc.id}
                        doc={doc}
                        isSelected={selectedDocId === doc.id}
                        isDeleting={deletingId === doc.id}
                        onSelect={() => onSelectDoc(doc)}
                        onDelete={(e) => handleDelete(e, doc.id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="px-4 py-3 border-t border-white/8">
          <p className="text-xs font-mono text-dot-dim/30 text-center">
            {readyCount}/{documents.length} ready · {libraryDocs.length} library · {chatDocs.length} chat
          </p>
        </div>
      </aside>

      {/* Desktop collapsed toggle */}
      {!isOpen && (
        <button
          onClick={onToggle}
          title="Open sidebar"
          className="hidden md:flex flex-col items-center justify-center
                     w-10 h-full border-r border-white/8 bg-dot-dark
                     hover:bg-white/3 transition-colors flex-shrink-0"
        >
          <PanelLeftOpen className="w-4 h-4 text-dot-dim" />
        </button>
      )}
    </>
  );
}
