import React, { useState } from 'react';
import { Folder, FolderPlus, RefreshCw, Trash2, Loader2 } from 'lucide-react';
import { FolderItem, IndexingStatus } from '../../api/types';

interface FolderManagerProps {
  folders: FolderItem[];
  indexingStatus: IndexingStatus;
  onAddFolder: (path: string) => void;
  onRemoveFolder: (path: string) => void;
  onRescanFolder: (path: string) => void;
}

export const FolderManager: React.FC<FolderManagerProps> = ({
  folders,
  indexingStatus,
  onAddFolder,
  onRemoveFolder,
  onRescanFolder,
}) => {
  const [inputPath, setInputPath] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const handleManualAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputPath.trim()) {
      onAddFolder(inputPath.trim());
      setInputPath('');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      // On desktop Electron, file.path is available
      const p = (file as any).path || file.name;
      if (p) onAddFolder(p);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 p-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Folder Library & Indexing</h2>
        <p className="text-xs text-zinc-400 mt-1">
          Manage local folders indexed for neural search, OCR extraction, and visual understanding.
        </p>
      </div>

      {/* Live Indexing Progress Banner (if active) */}
      {indexingStatus.is_scanning && (
        <div className="p-4 rounded-2xl bg-sky-500/10 border border-sky-500/25 space-y-2 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-sky-300 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
              Indexing in progress...
            </span>
            <span className="font-mono text-sky-200">
              {indexingStatus.current_count} / {indexingStatus.total_count} files
            </span>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-sky-400 to-indigo-500 transition-all duration-300"
              style={{
                width: `${
                  indexingStatus.total_count > 0
                    ? (indexingStatus.current_count / indexingStatus.total_count) * 100
                    : 15
                }%`,
              }}
            />
          </div>

          <div className="text-[11px] font-mono text-zinc-400 truncate">
            Current: {indexingStatus.current_file || indexingStatus.current_folder}
          </div>
        </div>
      )}

      {/* Folder Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center p-8 rounded-2xl border-2 border-dashed transition-all duration-200 text-center ${
          isDragging
            ? 'border-sky-400 bg-sky-500/10 scale-[1.01]'
            : 'border-white/10 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]'
        }`}
      >
        <div className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/[0.08] mb-3">
          <FolderPlus className="w-7 h-7 text-sky-400" />
        </div>
        <h4 className="text-sm font-semibold text-white mb-1">Drag and drop a folder here</h4>
        <p className="text-xs text-zinc-500 mb-4 max-w-sm">
          Drop any directory to index all documents, photos, code, and videos for instant AI retrieval.
        </p>

        {/* Path Input Alternative */}
        <form onSubmit={handleManualAdd} className="flex items-center gap-2 w-full max-w-md">
          <input
            type="text"
            value={inputPath}
            onChange={(e) => setInputPath(e.target.value)}
            placeholder="C:\Users\username\Documents..."
            className="flex-1 px-3.5 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white placeholder-zinc-500 outline-none focus:border-sky-400"
          />
          <button
            type="submit"
            className="btn-white px-4 py-2 rounded-xl font-bold text-xs hover:bg-zinc-200 transition-colors shrink-0 shadow-sm"
            style={{ color: '#09090b', backgroundColor: '#ffffff' }}
          >
            Add Folder
          </button>
        </form>
      </div>

      {/* Indexed Folders List */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          Watched Folders ({folders.length})
        </h3>

        <div className="space-y-2">
          {folders.map((f) => (
            <div
              key={f.id}
              className="flex items-center justify-between p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-colors"
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="p-2.5 rounded-xl bg-white/[0.05] border border-white/[0.08] text-sky-400">
                  <Folder className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <span className="font-semibold text-white text-sm block truncate" title={f.path}>
                    {f.path.split(/[\\/]/).pop() || f.path}
                  </span>
                  <span className="text-xs text-zinc-500 font-mono block truncate" title={f.path}>
                    {f.path}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <span className="text-xs font-semibold text-white font-mono block">
                    {f.file_count.toLocaleString()} files
                  </span>
                  <span className="text-[11px] text-zinc-500 block">
                    {f.last_scanned_at ? `Scanned ${f.last_scanned_at.slice(0, 10)}` : 'Pending scan'}
                  </span>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => onRescanFolder(f.path)}
                    className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
                    title="Rescan folder"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveFolder(f.path)}
                    className="p-2 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Remove from index"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}

          {folders.length === 0 && (
            <div className="p-8 text-center text-zinc-500 text-xs rounded-2xl bg-white/[0.01] border border-white/[0.04]">
              No folders added yet. Add a folder above to start indexing.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
