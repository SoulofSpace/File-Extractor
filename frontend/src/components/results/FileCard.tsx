import React, { useState } from 'react';
import { FileText, Image as ImageIcon, Film, Music, Code2, Archive, ExternalLink, Sparkles } from 'lucide-react';
import { SearchResultItem } from '../../api/types';
import { apiClient } from '../../api/client';
import { MatchEvidenceView } from './MatchEvidenceView';

interface FileCardProps {
  file: SearchResultItem;
  isSelected: boolean;
  onSelect: (file: SearchResultItem) => void;
  onOpen: (path: string) => void;
}

export const FileCard: React.FC<FileCardProps> = ({ file, isSelected, onSelect, onOpen }) => {
  const [imgError, setImgError] = useState(false);

  const formatSize = (bytes?: number) => {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + (sizes[i] || 'B');
  };

  const formatDate = (dateVal?: string | number) => {
    if (!dateVal) return '—';
    try {
      const num = typeof dateVal === 'number' ? dateVal : parseFloat(String(dateVal));
      if (!isNaN(num) && num > 0) {
        const ms = num < 1e11 ? num * 1000 : num;
        return new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
      }
      const d = new Date(dateVal);
      if (isNaN(d.getTime())) return String(dateVal).slice(0, 10);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return String(dateVal).slice(0, 10);
    }
  };

  const ext = (file.extension || '').toLowerCase();
  const isImage = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(ext);
  const isVideo = ['.mp4', '.mkv', '.avi', '.mov', '.webm'].includes(ext);
  const isAudio = ['.mp3', '.wav', '.flac', '.m4a'].includes(ext);
  const isCode = ['.py', '.js', '.ts', '.tsx', '.jsx', '.c', '.cpp', '.html', '.css', '.json', '.sql'].includes(ext);

  const getFileIcon = () => {
    if (isImage) return <ImageIcon className="w-5 h-5 text-sky-400" />;
    if (isVideo) return <Film className="w-5 h-5 text-rose-400" />;
    if (isAudio) return <Music className="w-5 h-5 text-amber-400" />;
    if (isCode) return <Code2 className="w-5 h-5 text-emerald-400" />;
    if (['.zip', '.rar', '.7z', '.tar', '.gz'].includes(ext))
      return <Archive className="w-5 h-5 text-purple-400" />;
    return <FileText className="w-5 h-5 text-zinc-400" />;
  };

  return (
    <div
      onClick={() => onSelect(file)}
      onDoubleClick={() => onOpen(file.path)}
      className={`group relative flex flex-col justify-between rounded-2xl p-4 transition-all duration-200 cursor-pointer select-none border backdrop-blur-md ${
        isSelected
          ? 'bg-[#1e2029]/95 border-sky-500/50 shadow-[0_12px_36px_rgba(14,165,233,0.15)] ring-1 ring-sky-500/30'
          : 'bg-[#15161b]/60 border-white/[0.08] hover:bg-[#1a1c23]/80 hover:border-white/20 hover:shadow-[0_8px_30px_rgba(0,0,0,0.5)]'
      }`}
    >
      {/* Top Media Thumbnail / Visual Canvas */}
      <div className="relative w-full h-36 rounded-xl overflow-hidden bg-black/40 border border-white/[0.05] flex items-center justify-center mb-3">
        {isImage && !imgError ? (
          <img
            src={apiClient.getThumbnailUrl(file.file_id, 400)}
            alt={file.filename || ''}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 p-4 text-center">
            <div className="p-3 rounded-2xl bg-white/[0.04] border border-white/[0.06]">
              {getFileIcon()}
            </div>
            <span className="font-mono text-[11px] text-zinc-400 uppercase font-semibold">
              {ext.replace('.', '') || file.file_type || file.category || 'FILE'}
            </span>
          </div>
        )}

        {/* Floating Relevance Score Pill */}
        {file.relevance_score > 0 && (
          <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-white font-mono text-[10px] font-medium flex items-center gap-1 shadow-sm">
            <Sparkles className="w-2.5 h-2.5 text-sky-400" />
            <span>{(file.relevance_score * 100).toFixed(0)}%</span>
          </div>
        )}

        {/* Floating Quick Open Action Button */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpen(file.path);
          }}
          className="absolute bottom-2.5 right-2.5 p-1.5 rounded-lg bg-white/10 hover:bg-white text-zinc-300 hover:text-black backdrop-blur-md border border-white/10 transition-all opacity-0 group-hover:opacity-100 shadow-lg"
          title="Open in default app"
        >
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Card Body */}
      <div className="space-y-1.5 flex-1">
        {/* Title */}
        <h4
          className="text-sm font-semibold text-white truncate group-hover:text-sky-300 transition-colors"
          title={file.filename}
        >
          {file.filename}
        </h4>

        {/* Snippet / Description Preview */}
        {file.snippet && (
          <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
            {file.snippet}
          </p>
        )}

        {/* Compact Match Evidence Tags */}
        <div className="pt-1">
          <MatchEvidenceView evidence={file.match_evidence} compact />
        </div>
      </div>

      {/* Card Footer: Metadata (Size & Date) */}
      <div className="flex items-center justify-between pt-3 mt-2 border-t border-white/[0.06] text-[11px] text-zinc-500 font-medium">
        <span>{formatSize(file.size_bytes)}</span>
        <span>{formatDate(file.modified_at)}</span>
      </div>
    </div>
  );
};
