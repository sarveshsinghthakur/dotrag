import { useState } from 'react';
import {
  Menu, X, FileText, Trash2, RefreshCw, Plus,
  MessageSquare
} from 'lucide-react';
import type { Document } from '../types';
import UploadZone from './UploadZone';

interface SidebarProps {
  documents: Document[];
  isOpen: boolean;
  onToggle: () => void;
  onSelectDoc: (doc: Document) => void;
  onOpenChat: (docIds?: string[]) => void;
  onDelete: (id: string) => void;
  onUpload: (file: File) => Promise<unknown>;
  onRefresh: () => void;
  selectedDocId?: string;
  loading: boolean;
}

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
}: SidebarProps) {
  const [showUpload, setShowUpload] = useState(false);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'text-white';
      case 'processing':
      case 'indexing': return 'text-dot-dim';
      case 'error': return 'text-red-400';
      default: return 'text-dot-dim';
    }
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="fixed top-4 left-4 z-40 p-2 bg-dot-dark border border-dot-dim/30
                   hover:border-white/50 transition-colors md:hidden"
      >
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Sidebar */}
      <aside
        className={`
          fixed md:relative z-30 h-full
          w-72 bg-dot-dark border-r border-dot-dim/20
          flex flex-col transition-transform duration-200
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:overflow-hidden'}
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-dot-dim/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-white rounded-full"></div>
              <span className="font-mono text-sm font-bold tracking-wider">DOTRAG</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={onRefresh}
                className="p-1.5 hover:bg-white/10 transition-colors"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4 text-dot-dim" />
              </button>
            </div>
          </div>
        </div>

        {/* Upload section */}
        <div className="p-3 border-b border-dot-dim/20">
          {showUpload ? (
            <div className="space-y-2">
              <UploadZone onUpload={onUpload} />
              <button
                onClick={() => setShowUpload(false)}
                className="w-full text-xs text-dot-dim hover:text-white py-1"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowUpload(true)}
              className="w-full flex items-center justify-center gap-2 py-2.5
                         border border-dot-dim/30 hover:border-white/50
                         text-sm font-mono text-dot-dim hover:text-white
                         transition-all duration-200"
            >
              <Plus className="w-4 h-4" />
              Upload PDF
            </button>
          )}
        </div>

        {/* Research button */}
        <div className="p-3 border-b border-dot-dim/20">
          <button
            onClick={() => {
              const readyDocs = documents.filter(d => d.status === 'ready');
              onOpenChat(readyDocs.map(d => d.id));
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5
                       bg-white text-black text-sm font-mono font-medium
                       hover:bg-gray-200 transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            Research Session
          </button>
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-3">
            <h3 className="text-xs font-mono text-dot-dim tracking-wider mb-3">
              DOCUMENTS
            </h3>

            {loading ? (
              <div className="text-xs text-dot-dim font-mono py-4 text-center">
                Loading...
              </div>
            ) : documents.length === 0 ? (
              <div className="text-xs text-dot-dim/50 font-mono py-4 text-center">
                No documents uploaded
              </div>
            ) : (
              <div className="space-y-1">
                {documents.map((doc, idx) => (
                  <div
                    key={doc.id}
                    className={`
                      group p-3 border transition-all duration-150 cursor-pointer
                      ${selectedDocId === doc.id
                        ? 'border-white bg-white/5'
                        : 'border-transparent hover:border-dot-dim/30'
                      }
                    `}
                    onClick={() => onSelectDoc(doc)}
                  >
                    <div className="flex items-start gap-3">
                      <FileText className="w-4 h-4 mt-0.5 text-dot-dim flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-dot-dim">
                            {String(idx + 1).padStart(2, '0')}
                          </span>
                          <span className="text-sm truncate">{doc.filename}</span>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-dot-dim/60">
                          <span>{formatSize(doc.file_size)}</span>
                          <span>{doc.page_count} pages</span>
                          <span className={getStatusColor(doc.status)}>
                            {doc.status}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(doc.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1
                                   hover:bg-white/10 transition-all"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3 text-dot-dim hover:text-red-400" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-dot-dim/20">
          <div className="text-xs font-mono text-dot-dim/40 text-center">
            {documents.length} document{documents.length !== 1 ? 's' : ''} loaded
          </div>
        </div>
      </aside>
    </>
  );
}
