import { useState, useRef } from 'react';
import { Upload, FileText, Image as ImageIcon, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

const ACCEPTED = '.pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.tif,.webp';
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'image/jpeg', 'image/png', 'image/gif',
  'image/bmp', 'image/tiff', 'image/webp',
]);

function getFileLabel(file: File): string {
  if (file.type === 'application/pdf') return 'PDF';
  if (file.type.startsWith('image/')) return 'Image';
  return 'File';
}

interface UploadZoneProps {
  onUpload: (file: File) => Promise<unknown>;
  /** Compact mode for sidebar */
  compact?: boolean;
  /** Disable the zone */
  disabled?: boolean;
}

export default function UploadZone({ onUpload, compact = false, disabled = false }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_MIME.has(file.type)) {
      return 'Unsupported type. Use PDF or image files.';
    }
    if (file.size > 100 * 1024 * 1024) {
      return 'File exceeds 100 MB limit.';
    }
    return null;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !uploading) setIsDragging(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled || uploading) return;
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) {
      setError(err);
      setTimeout(() => setError(null), 3500);
      return;
    }
    await handleUpload(file);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) {
      setError(err);
      setTimeout(() => setError(null), 3500);
      return;
    }
    await handleUpload(file);
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setProgress(0);
    setError(null);
    setDone(false);
    setCurrentFile(file);

    const interval = setInterval(() => {
      setProgress((p) => Math.min(p + 8, 88));
    }, 180);

    try {
      await onUpload(file);
      clearInterval(interval);
      setProgress(100);
      setDone(true);
      setTimeout(() => { setDone(false); setProgress(0); setCurrentFile(null); }, 2200);
    } catch (err: unknown) {
      clearInterval(interval);
      const msg = err instanceof Error ? err.message : 'Upload failed — please try again';
      setError(msg);
      setTimeout(() => setError(null), 4000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const clickable = !uploading && !disabled;

  // ─── Compact variant ──────────────────────────────────────────────────────
  if (compact) {
    return (
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => clickable && fileInputRef.current?.click()}
        className={`
          relative border border-dashed p-3 transition-all
          ${clickable ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'}
          ${isDragging ? 'border-white/40 bg-white/5' : 'border-white/15 hover:border-white/30 hover:bg-white/3'}
        `}
      >
        <input ref={fileInputRef} type="file" accept={ACCEPTED} onChange={handleFileSelect} className="hidden" />
        <div className="flex items-center gap-2">
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-dot-dim flex-shrink-0" />
              <div className="flex-1">
                <div className="text-xs font-mono text-dot-dim truncate max-w-[120px]">
                  {currentFile?.name ?? 'Uploading…'} {progress}%
                </div>
                <div className="h-0.5 bg-dot-dim/20 mt-1">
                  <div className="h-full bg-white transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
              </div>
            </>
          ) : done ? (
            <>
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span className="text-xs font-mono text-emerald-400">Uploaded!</span>
            </>
          ) : error ? (
            <>
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span className="text-xs font-mono text-red-400 truncate">{error}</span>
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 text-dot-dim flex-shrink-0" />
              <span className="text-xs font-mono text-dot-dim">
                {isDragging ? 'Drop here' : 'Click or drag · PDF / Image'}
              </span>
            </>
          )}
        </div>
      </div>
    );
  }

  // ─── Full-size variant ────────────────────────────────────────────────────
  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => clickable && fileInputRef.current?.click()}
      className={`
        relative border-2 border-dashed p-10 transition-all duration-200 group
        ${clickable ? 'cursor-pointer' : 'cursor-not-allowed'}
        ${isDragging ? 'border-white bg-white/5' : 'border-white/20 hover:border-white/50 hover:bg-white/2'}
        ${uploading ? 'opacity-90' : ''}
      `}
    >
      <input ref={fileInputRef} type="file" accept={ACCEPTED} onChange={handleFileSelect} className="hidden" />

      <div className="flex flex-col items-center gap-4">
        {uploading ? (
          <>
            <div className="w-16 h-16 flex items-center justify-center border border-white/20 bg-white/3">
              <Loader2 className="w-7 h-7 animate-spin text-white" />
            </div>
            <div className="text-center space-y-2">
              <p className="font-mono text-sm text-white">
                {getFileLabel(currentFile!)} uploading… {progress}%
              </p>
              <div className="w-48 h-0.5 bg-white/10 overflow-hidden">
                <div className="h-full bg-white transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
            </div>
          </>
        ) : done ? (
          <>
            <div className="w-16 h-16 flex items-center justify-center border border-emerald-500/30 bg-emerald-500/10">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <p className="font-mono text-sm text-emerald-400">Uploaded! Processing…</p>
          </>
        ) : error ? (
          <>
            <div className="w-16 h-16 flex items-center justify-center border border-red-500/30 bg-red-500/10">
              <AlertCircle className="w-7 h-7 text-red-400" />
            </div>
            <p className="font-mono text-sm text-red-400 text-center max-w-xs">{error}</p>
          </>
        ) : (
          <>
            <div className="w-16 h-16 flex items-center justify-center border border-white/15 group-hover:border-white/40 transition-colors bg-white/3">
              {isDragging ? (
                <FileText className="w-7 h-7 text-white" />
              ) : (
                <Upload className="w-7 h-7 text-dot-dim group-hover:text-white transition-colors" />
              )}
            </div>
            <div className="text-center space-y-1.5">
              <p className="font-mono text-sm text-dot-dim group-hover:text-white transition-colors">
                {isDragging ? 'Drop your file here' : '+ Upload File'}
              </p>
              <p className="text-xs text-dot-dim/40">
                PDF or image (JPG, PNG, GIF, BMP, TIFF, WebP) · up to 100 MB
              </p>
              <div className="flex items-center justify-center gap-3 pt-1">
                <div className="flex items-center gap-1 text-dot-dim/40">
                  <FileText className="w-3 h-3" />
                  <span className="text-xs font-mono">PDF</span>
                </div>
                <div className="flex items-center gap-1 text-dot-dim/40">
                  <ImageIcon className="w-3 h-3" />
                  <span className="text-xs font-mono">Images</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
