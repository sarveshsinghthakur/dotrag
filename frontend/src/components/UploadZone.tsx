import { useState, useRef } from 'react';
import { Upload, FileText, Loader2 } from 'lucide-react';

interface UploadZoneProps {
  onUpload: (file: File) => Promise<unknown>;
}

export default function UploadZone({ onUpload }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      await handleUpload(file);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await handleUpload(file);
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setProgress(0);
    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      await onUpload(file);
      clearInterval(progressInterval);
      setProgress(100);
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setTimeout(() => {
        setUploading(false);
        setProgress(0);
      }, 500);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
      className={`
        relative cursor-pointer border-2 border-dashed p-12
        transition-all duration-200 group
        ${isDragging
          ? 'border-white bg-white/5'
          : 'border-dot-dim/30 hover:border-white/50'
        }
        ${uploading ? 'pointer-events-none' : ''}
      `}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        className="hidden"
      />

      <div className="flex flex-col items-center gap-4">
        {uploading ? (
          <>
            <Loader2 className="w-8 h-8 animate-spin text-white" />
            <div className="font-mono text-sm text-dot-dim">
              Processing... {progress}%
            </div>
            <div className="w-48 h-1 bg-dot-dark overflow-hidden">
              <div
                className="h-full bg-white transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </>
        ) : (
          <>
            <div className="p-4 border border-dot-dim/30 group-hover:border-white/50 transition-colors">
              {isDragging ? (
                <FileText className="w-8 h-8 text-white" />
              ) : (
                <Upload className="w-8 h-8 text-dot-dim group-hover:text-white transition-colors" />
              )}
            </div>
            <div className="space-y-2">
              <p className="font-mono text-sm text-dot-dim group-hover:text-white transition-colors">
                {isDragging ? 'Drop PDF here' : '+ Upload PDF'}
              </p>
              <p className="text-xs text-dot-dim/50">
                PDF files up to 100MB
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
