import React from 'react';
import { FileText, Image as ImageIcon, Film, Music, Code2, Archive, ExternalLink } from 'lucide-react';
import { SearchResultItem } from '../../api/types';
import { apiClient } from '../../api/client';

interface FileListProps {
  files: SearchResultItem[];
  selectedFile: SearchResultItem | null;
  onSelectFile: (file: SearchResultItem) => void;
  onOpenFile: (path: string) => void;
}

export const FileList: React.FC<FileListProps> = ({
  files,
  selectedFile,
  onSelectFile,
  onOpenFile,
}) => {
  const formatSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr.slice(0, 10);
    }
  };

  const getFileIcon = (ext: string) => {
    const e = ext.toLowerCase();
    if (['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(e))
      return <ImageIcon className="w-4 h-4 text-sky-400" />;
    if (['.mp4', '.mkv', '.avi', '.mov', '.webm'].includes(e))
      return <Film className="w-4 h-4 text-rose-400" />;
    if (['.mp3', '.wav', '.flac', '.m4a'].includes(e))
      return <Music className="w-4 h-4 text-amber-400" />;
    if (['.py', '.js', '.ts', '.tsx', '.jsx', '.c', '.cpp', '.html', '.css', '.json', '.sql'].includes(e))
      return <Code2 className="w-4 h-4 text-emerald-400" />;
    if (['.zip', '.rar', '.7z'].includes(e))
      return <Archive className="w-4 h-4 text-purple-400" />;
    return <FileText className="w-4 h-4 text-zinc-400" />;
  };

  return (
    <div className="space-y-1.5 p-1">
      {/* Table Header */}
      <div className="grid grid-cols-12 gap-3 px-4 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider border-b border-white/[0.06]">
        <span className="col-span-6">Name</span>
        <span className="col-span-2">Type / Category</span>
        <span className="col-span-2">Date Modified</span>
        <span className="col-span-1 text-right">Size</span>
        <span className="col-span-1 text-right">Relevance</span>
      </div>

      {/* Rows */}
      {files.map((file) => {
        const isSelected = selectedFile?.file_id === file.file_id;
        const isImage = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(file.extension.toLowerCase());

        return (
          <div
            key={`${file.file_id}-${file.path}`}
            onClick={() => onSelectFile(file)}
            onDoubleClick={() => onOpenFile(file.path)}
            className={`grid grid-cols-12 gap-3 items-center px-4 py-3 rounded-xl border transition-all duration-150 cursor-pointer select-none text-xs ${
              isSelected
                ? 'bg-[#1e2029]/95 border-sky-500/50 shadow-md ring-1 ring-sky-500/20'
                : 'bg-[#14151a]/50 border-white/[0.05] hover:bg-[#1a1c22]/80 hover:border-white/15'
            }`}
          >
            {/* Name + Icon */}
            <div className="col-span-6 flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-black/40 border border-white/[0.06] overflow-hidden flex items-center justify-center shrink-0">
                {isImage ? (
                  <img
                    src={apiClient.getThumbnailUrl(file.file_id, 100)}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  getFileIcon(file.extension)
                )}
              </div>
              <div className="min-w-0">
                <span className="font-semibold text-white truncate block hover:text-sky-300 transition-colors" title={file.filename}>
                  {file.filename}
                </span>
                <span className="text-[11px] text-zinc-500 truncate block font-mono">
                  {file.path}
                </span>
              </div>
            </div>

            {/* Type / Category */}
            <div className="col-span-2 flex items-center gap-1.5">
              <span className="px-2 py-0.5 rounded-md bg-white/[0.05] text-zinc-300 border border-white/[0.06] text-[11px] font-medium uppercase font-mono">
                {file.extension.replace('.', '') || file.category}
              </span>
            </div>

            {/* Date Modified */}
            <div className="col-span-2 text-zinc-400">
              {formatDate(file.modified_at)}
            </div>

            {/* Size */}
            <div className="col-span-1 text-right text-zinc-400 font-mono">
              {formatSize(file.size_bytes)}
            </div>

            {/* Score & Actions */}
            <div className="col-span-1 flex items-center justify-end gap-2">
              {file.relevance_score > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-sky-500/15 text-sky-300 font-mono text-[10px] font-medium border border-sky-500/25">
                  {(file.relevance_score * 100).toFixed(0)}%
                </span>
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(file.path);
                }}
                className="p-1 rounded text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
                title="Open file"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
