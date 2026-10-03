import React from 'react';
import { SearchBar } from '../search/SearchBar';
import {
  FileText,
  Image as ImageIcon,
  Film,
  Music,
  Code2,
  Archive,
  Clock,
  HardDrive,
  ExternalLink,
} from 'lucide-react';
import { SearchResultItem } from '../../api/types';
import { apiClient } from '../../api/client';

interface HeroSearchProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSearch: (q: string) => void;
  isLoading: boolean;
  onSelectCategory: (cat: string) => void;
  categoryCounts?: Record<string, number>;
  totalFiles?: number;
  recentFiles?: SearchResultItem[];
  recentSearches?: string[];
  onOpenFile?: (path: string) => void;
  onSelectFile?: (file: SearchResultItem) => void;
}

export const HeroSearch: React.FC<HeroSearchProps> = ({
  query,
  onQueryChange,
  onSearch,
  isLoading,
  onSelectCategory,
  categoryCounts = {},
  totalFiles = 0,
  recentFiles = [],
  recentSearches = [],
  onOpenFile,
  onSelectFile,
}) => {
  const libraryCards = [
    {
      id: 'DOCUMENT',
      label: 'Documents',
      icon: <FileText className="w-5 h-5 text-emerald-400" />,
      count: categoryCounts['DOCUMENT'] ?? 0,
      description: 'PDF, Word, Slides, Sheets',
    },
    {
      id: 'IMAGE',
      label: 'Images',
      icon: <ImageIcon className="w-5 h-5 text-sky-400" />,
      count: categoryCounts['IMAGE'] ?? 0,
      description: 'Photos, Screenshots, Graphics',
    },
    {
      id: 'VIDEO',
      label: 'Videos',
      icon: <Film className="w-5 h-5 text-rose-400" />,
      count: categoryCounts['VIDEO'] ?? 0,
      description: 'MP4, MKV, Clips, Movies',
    },
    {
      id: 'AUDIO',
      label: 'Audio',
      icon: <Music className="w-5 h-5 text-amber-400" />,
      count: categoryCounts['AUDIO'] ?? 0,
      description: 'Music, Sound, Recordings',
    },
    {
      id: 'CODE',
      label: 'Code',
      icon: <Code2 className="w-5 h-5 text-purple-400" />,
      count: categoryCounts['CODE'] ?? 0,
      description: 'Python, Web, Scripts',
    },
    {
      id: 'ARCHIVE',
      label: 'Archives',
      icon: <Archive className="w-5 h-5 text-indigo-400" />,
      count: categoryCounts['ARCHIVE'] ?? 0,
      description: 'ZIP, RAR, 7Z Packages',
    },
  ];

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

  return (
    <div className="relative z-10 flex flex-col items-center justify-start w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 select-none py-2">
      {/* 1. Header: 6-Petal Asterisk + "Hey There!" (Direct from Reference Image) */}
      <div className="flex items-center justify-center gap-3.5 pt-4">
        <svg
          className="w-10 h-10 sm:w-12 sm:h-12 text-white fill-current shrink-0 drop-shadow-[0_4px_12px_rgba(255,255,255,0.2)]"
          viewBox="0 0 48 48"
        >
          {/* Symmetrical 6-petal chunky rounded starburst matching reference */}
          <rect x="20" y="4" width="8" height="40" rx="4" transform="rotate(0 24 24)" />
          <rect x="20" y="4" width="8" height="40" rx="4" transform="rotate(60 24 24)" />
          <rect x="20" y="4" width="8" height="40" rx="4" transform="rotate(120 24 24)" />
        </svg>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-white font-sans drop-shadow-sm">
          Hey There!
        </h1>
      </div>

      {/* 2. Floating Island Search Box (Direct from Reference Image) */}
      <div className="w-full max-w-2xl px-2">
        <SearchBar
          query={query}
          onChange={onQueryChange}
          onSearch={onSearch}
          isLoading={isLoading}
          autoFocus={true}
          variant="island"
          placeholder="Search what you want over here..."
        />
      </div>

      {/* 3. Large Bottom Island Container (Direct from Reference Image) */}
      <div className="w-full rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 md:p-8 flex flex-col gap-6 text-black">
        {/* Upper Row: Browse by Library */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-800 font-mono">
              Browse by Library
            </span>
            <span className="text-xs font-semibold text-zinc-600 font-mono">
              {totalFiles.toLocaleString()} files indexed
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            {libraryCards.map((card) => (
              <button
                key={card.id}
                type="button"
                onClick={() => onSelectCategory(card.id)}
                className="group relative flex flex-col items-start p-3.5 rounded-2xl bg-[#090a0f] hover:bg-black text-white border border-white/10 hover:border-white/25 transition-all duration-150 text-left shadow-md hover:shadow-xl hover:scale-[1.02]"
              >
                <div className="p-2 rounded-xl bg-white/[0.08] border border-white/10 mb-3 group-hover:scale-105 transition-transform">
                  {card.icon}
                </div>
                <span className="text-sm font-semibold text-white group-hover:text-sky-300 transition-colors">
                  {card.label}
                </span>
                <span className="text-[11px] font-mono text-zinc-400 mt-0.5">
                  {card.count.toLocaleString()} files
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Middle Row: Recently Indexed Files */}
        {recentFiles && recentFiles.length > 0 && (
          <div className="space-y-3 pt-2 border-t border-black/10">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-800 font-mono">
                Recently Indexed Files
              </span>
              <span className="text-xs text-zinc-600 font-medium">
                Double-click to open
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {recentFiles.slice(0, 8).map((file) => {
                const ext = (file.extension || '').toLowerCase();
                const isImage = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(ext);

                return (
                  <div
                    key={`${file.file_id}-${file.path}`}
                    onClick={() => onSelectFile && onSelectFile(file)}
                    onDoubleClick={() => onOpenFile && onOpenFile(file.path)}
                    className="group relative flex items-center gap-3 p-3 rounded-2xl bg-[#090a0f] hover:bg-black text-white border border-white/10 hover:border-white/25 transition-all duration-150 cursor-pointer select-none shadow-md hover:shadow-lg hover:scale-[1.01]"
                  >
                    <div className="w-10 h-10 rounded-xl bg-black/60 border border-white/10 overflow-hidden flex items-center justify-center shrink-0">
                      {isImage ? (
                        <img
                          src={apiClient.getThumbnailUrl(file.file_id, 120)}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <FileText className="w-5 h-5 text-zinc-400" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <span
                        className="font-medium text-xs text-white truncate block group-hover:text-sky-300 transition-colors"
                        title={file.filename || ''}
                      >
                        {file.filename || 'Untitled'}
                      </span>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-400 mt-0.5 font-mono">
                        <span>{formatSize(file.size_bytes)}</span>
                        <span>•</span>
                        <span>{formatDate(file.modified_at)}</span>
                      </div>
                    </div>

                    {onOpenFile && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenFile(file.path);
                        }}
                        className="p-1 rounded text-zinc-400 hover:text-white hover:bg-white/15 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                        title="Open file"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Lower Row: Recent Searches & Offline Indicator */}
        <div className="flex items-center justify-between gap-4 flex-wrap pt-2 border-t border-black/10 text-xs">
          {recentSearches.length > 0 ? (
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1.5 text-zinc-700 font-bold">
                <Clock className="w-3.5 h-3.5" />
                <span>Recent:</span>
              </div>
              {recentSearches.slice(0, 5).map((s, idx) => (
                <button
                  key={`${s}-${idx}`}
                  type="button"
                  onClick={() => {
                    onQueryChange(s);
                    onSearch(s);
                  }}
                  className="px-3 py-1 rounded-xl bg-black text-white hover:bg-zinc-800 transition-colors font-mono text-[11px] font-medium shadow-sm hover:scale-105"
                >
                  {s}
                </button>
              ))}
            </div>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-black/80 text-white font-medium text-[11px] shadow-sm ml-auto">
            <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
            <span>100% Offline & Private Local Indexing</span>
          </div>
        </div>
      </div>
    </div>
  );
};
