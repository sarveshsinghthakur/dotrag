import { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import {
  ArrowLeft, MessageSquare, FileText,
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut,
  Loader2, AlertCircle, Maximize2, Minimize2
} from 'lucide-react';
import { api } from '../services/api';
import type { Document as DocType } from '../types';

// ─── PDF.js worker ────────────────────────────────────────────────────────────
// Use the CDN worker that matches the installed pdfjs-dist version.
// When using Vite, importing via new URL() requires the file to be in /public,
// so we use the CDN approach which is simpler and reliable.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// ─── Props ────────────────────────────────────────────────────────────────────
interface PDFViewerProps {
  document: DocType;
  onBack: () => void;
  onOpenChat: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function PDFViewer({ document, onBack, onOpenChat }: PDFViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);

  const fileUrl = api.getDocumentFileUrl(document.id);
  const totalPages = numPages ?? document.page_count;
  const scale = zoom / 100;

  const onDocumentLoadSuccess = useCallback(
    ({ numPages: n }: { numPages: number }) => {
      setNumPages(n);
      setError(null);
    },
    []
  );

  const onDocumentLoadError = useCallback((err: Error) => {
    setError(err.message || 'Failed to load PDF');
  }, []);

  const onPageLoadSuccess = useCallback(() => {
    setPageLoading(false);
  }, []);

  const goTo = (page: number) => {
    setCurrentPage(Math.max(1, Math.min(totalPages, page)));
    setPageLoading(true);
  };

  const handleZoomIn = () => setZoom((z) => Math.min(200, z + 10));
  const handleZoomOut = () => setZoom((z) => Math.max(50, z - 10));

  return (
    <div className={`flex flex-col h-full bg-dot-black ${fullscreen ? 'fixed inset-0 z-50' : ''}`}>
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-dot-dark/80 backdrop-blur-sm flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onBack}
            className="p-1.5 rounded hover:bg-white/10 transition-colors flex-shrink-0"
            aria-label="Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-4 h-4 text-dot-dim flex-shrink-0" />
            <span className="font-mono text-sm truncate max-w-[240px]">{document.filename}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Page navigation */}
          <div className="flex items-center border border-white/10">
            <button
              onClick={() => goTo(currentPage - 1)}
              disabled={currentPage <= 1}
              className="p-1.5 hover:bg-white/10 disabled:opacity-30 transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2.5 py-1 text-xs font-mono border-x border-white/10 min-w-[72px] text-center">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => goTo(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="p-1.5 hover:bg-white/10 disabled:opacity-30 transition-colors"
              aria-label="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Zoom */}
          <div className="flex items-center border border-white/10">
            <button
              onClick={handleZoomOut}
              className="p-1.5 hover:bg-white/10 transition-colors"
              aria-label="Zoom out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="px-2 py-1 text-xs font-mono border-x border-white/10 min-w-[52px] text-center">
              {zoom}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-1.5 hover:bg-white/10 transition-colors"
              aria-label="Zoom in"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          {/* Fullscreen toggle */}
          <button
            onClick={() => setFullscreen((f) => !f)}
            className="p-1.5 border border-white/10 hover:bg-white/10 transition-colors hidden md:block"
            aria-label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {fullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          {/* Chat button */}
          <button
            onClick={onOpenChat}
            className="flex items-center gap-2 px-3 py-1.5 bg-white text-black
                       text-xs font-mono font-medium hover:bg-gray-100 transition-colors"
          >
            <MessageSquare className="w-3 h-3" />
            Ask about this
          </button>
        </div>
      </div>

      {/* ── PDF Content ── */}
      <div className="flex-1 overflow-auto dot-matrix-bg">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-red-400">
            <AlertCircle className="w-12 h-12" />
            <p className="font-mono text-sm">{error}</p>
            <button
              onClick={() => setError(null)}
              className="px-4 py-2 border border-red-400/50 text-xs font-mono
                         hover:bg-red-400/10 transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          /* We wrap the Document in a scroll container.
             We do NOT use CSS transform: scale() on the container because it
             causes the container to visually shrink while the content overflows
             invisibly. Instead we pass `scale` directly to the <Page> component
             which renders at the correct pixel size. */
          <div className="flex items-start justify-center min-h-full py-8 px-4">
            <Document
              file={fileUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={
                <div className="flex items-center justify-center w-[595px] h-[842px] bg-white shadow-lg rounded-sm">
                  <Loader2 className="w-8 h-8 animate-spin text-gray-300" />
                </div>
              }
              error={
                <div className="flex flex-col items-center justify-center w-[595px] h-[842px] bg-white shadow-lg gap-3">
                  <AlertCircle className="w-12 h-12 text-gray-400" />
                  <p className="font-mono text-sm text-gray-500">Failed to load PDF</p>
                </div>
              }
            >
              <div className="relative shadow-2xl">
                {pageLoading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                  </div>
                )}
                <Page
                  pageNumber={currentPage}
                  scale={scale}
                  className="block"
                  renderTextLayer
                  renderAnnotationLayer
                  onLoadSuccess={onPageLoadSuccess}
                />
              </div>
            </Document>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="px-4 py-2 border-t border-white/10 bg-dot-dark/80 flex items-center justify-between flex-shrink-0">
        <div className="text-xs font-mono text-dot-dim/50">
          {totalPages} pages · {(document.file_size / (1024 * 1024)).toFixed(1)} MB
        </div>
        <div className="flex items-center gap-3">
          {/* Keyboard hints */}
          <span className="text-xs text-dot-dim/30 font-mono hidden md:block">
            ← → navigate · +/- zoom
          </span>
          <div className="text-xs font-mono text-dot-dim/50">
            Page {currentPage} of {totalPages}
          </div>
        </div>
      </div>
    </div>
  );
}
