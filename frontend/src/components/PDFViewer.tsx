import { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import {
  ArrowLeft, MessageSquare, FileText,
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut,
  Loader2, AlertCircle
} from 'lucide-react';
import { api } from '../services/api';
import type { Document as DocType } from '../types';

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  document: DocType;
  onBack: () => void;
  onOpenChat: () => void;
}

export default function PDFViewer({ document, onBack, onOpenChat }: PDFViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileUrl = api.getDocumentFileUrl(document.id);

  const onDocumentLoadSuccess = useCallback(({ numPages: nextNumPages }: { numPages: number }) => {
    setNumPages(nextNumPages);
    setError(null);
  }, []);

  const onDocumentLoadError = useCallback((err: Error) => {
    setError(err.message || 'Failed to load PDF');
  }, []);

  const handlePrevPage = () => {
    setCurrentPage(p => Math.max(1, p - 1));
  };

  const handleNextPage = () => {
    setCurrentPage(p => Math.min(numPages || document.page_count, p + 1));
  };

  const scale = zoom / 100;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-dot-dim/20">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-dot-dim" />
            <span className="font-mono text-sm">{document.filename}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Page navigation */}
          <div className="flex items-center gap-1 border border-dot-dim/30">
            <button
              onClick={handlePrevPage}
              disabled={currentPage <= 1}
              className="p-1.5 hover:bg-white/10 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-xs font-mono border-x border-dot-dim/30">
              {currentPage} / {numPages || document.page_count}
            </span>
            <button
              onClick={handleNextPage}
              disabled={currentPage >= (numPages || document.page_count)}
              className="p-1.5 hover:bg-white/10 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Zoom */}
          <div className="flex items-center gap-1 border border-dot-dim/30">
            <button
              onClick={() => setZoom(z => Math.max(50, z - 10))}
              className="p-1.5 hover:bg-white/10 transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="px-2 py-1 text-xs font-mono border-x border-dot-dim/30 min-w-[50px] text-center">
              {zoom}%
            </span>
            <button
              onClick={() => setZoom(z => Math.min(200, z + 10))}
              className="p-1.5 hover:bg-white/10 transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          {/* Chat button */}
          <button
            onClick={onOpenChat}
            className="flex items-center gap-2 px-3 py-1.5 bg-white text-black
                       text-xs font-mono hover:bg-gray-200 transition-colors"
          >
            <MessageSquare className="w-3 h-3" />
            Ask about this
          </button>
        </div>
      </div>

      {/* PDF Content Area */}
      <div className="flex-1 overflow-auto bg-dot-gray/5 dot-matrix-bg">
        <div className="flex items-start justify-center min-h-full p-8">
          {error ? (
            <div className="flex flex-col items-center justify-center gap-4 text-red-400">
              <AlertCircle className="w-12 h-12" />
              <p className="font-mono text-sm">{error}</p>
              <button
                onClick={() => setError(null)}
                className="px-4 py-2 border border-red-400/50 text-xs font-mono hover:bg-red-400/10 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : (
            <div
              style={{ transform: `scale(${scale})`, transformOrigin: 'top center' }}
            >
              <Document
                file={fileUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={
                  <div className="flex items-center justify-center w-[595px] h-[842px] bg-white shadow-lg">
                    <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
                  </div>
                }
                error={
                  <div className="flex items-center justify-center w-[595px] h-[842px] bg-white shadow-lg">
                    <div className="text-center text-gray-400">
                      <AlertCircle className="w-12 h-12 mx-auto mb-4" />
                      <p className="font-mono text-sm">Failed to load PDF</p>
                    </div>
                  </div>
                }
              >
                <Page
                  pageNumber={currentPage}
                  width={595}
                  className="shadow-lg"
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                />
              </Document>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-dot-dim/20 flex items-center justify-between">
        <div className="text-xs font-mono text-dot-dim/50">
          {numPages || document.page_count} pages · {(document.file_size / (1024 * 1024)).toFixed(1)} MB
        </div>
        <div className="text-xs font-mono text-dot-dim/50">
          Page {currentPage} of {numPages || document.page_count}
        </div>
      </div>
    </div>
  );
}
