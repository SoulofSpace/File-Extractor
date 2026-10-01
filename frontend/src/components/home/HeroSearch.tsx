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
      description: 'MP4, MKV, Clips, Screen recordings',
    },
    {
      id: 'AUDIO',
      label: 'Audio',
      icon: <Music className="w-5 h-5 text-amber-400" />,
      count: categoryCounts['AUDIO'] ?? 0,
      description: 'Music, Recordings, Sound files',
    },
    {
      id: 'CODE',
      label: 'Code',
      icon: <Code2 className="w-5 h-5 text-purple-400" />,
      count: categoryCounts['CODE'] ?? 0,
      description: 'Python, Web, Scripts, Projects',
    },
    {
      id: 'ARCHIVE',
      label: 'Archives',
      icon: <Archive className="w-5 h-5 text-indigo-400" />,
      count: categoryCounts['ARCHIVE'] ?? 0,
      description: 'ZIP, RAR, 7Z packages',
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
    <div className="relative z-10 flex flex-col items-center justify-start w-full max-w-5xl mx-auto px-4 py-6 space-y-8 select-none">
      {/* 1. Desktop Header */}
      <div className="text-center space-y-2 pt-2">
        <div className="flex items-center justify-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <span className="text-white font-extrabold text-base tracking-wider font-mono">X</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            FILE XTRACTOR
          </h1>
        </div>
        <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto">
          Fast, private offline search across your local files, documents, and media.
        </p>
      </div>

      {/* 2. Main Search Bar */}
      <div className="w-full max-w-2xl">
        <SearchBar
          query={query}
          onChange={onQueryChange}
          onSearch={onSearch}
          isLoading={isLoading}
          autoFocus={true}
        />
      </div>

      {/* 3. Recent Searches (if any) */}
      {recentSearches.length > 0 && (
        <div className="flex items-center justify-center gap-2 flex-wrap text-xs text-zinc-400">
          <div className="flex items-center gap-1.5 text-zinc-500 font-medium">
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
              className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] border border-white/[0.06] text-zinc-300 hover:text-white transition-colors font-mono text-[11px]"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* 4. Library Categories Grid */}
      <div className="w-full space-y-3">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">
            Browse by Library
          </span>
          <span className="text-xs font-medium text-zinc-500">
            {totalFiles.toLocaleString()} files indexed
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {libraryCards.map((card) => (
            <button
              key={card.id}
              type="button"
              onClick={() => onSelectCategory(card.id)}
              className="group relative flex flex-col items-start p-3.5 rounded-2xl bg-[#14151b]/80 hover:bg-[#1a1c24] border border-white/[0.08] hover:border-white/20 transition-all duration-150 text-left shadow-sm hover:shadow-lg"
            >
              <div className="p-2 rounded-xl bg-white/[0.04] border border-white/[0.06] mb-3 group-hover:scale-105 transition-transform">
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

      {/* 5. Recently Added Files Grid */}
      {recentFiles && recentFiles.length > 0 && (
        <div className="w-full space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">
              Recently Indexed Files
            </span>
            <span className="text-xs text-zinc-500">
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
                  className="group relative flex items-center gap-3 p-3 rounded-xl bg-[#14151a]/60 hover:bg-[#1c1e27] border border-white/[0.06] hover:border-white/15 transition-all duration-150 cursor-pointer select-none"
                >
                  <div className="w-10 h-10 rounded-lg bg-black/40 border border-white/[0.06] overflow-hidden flex items-center justify-center shrink-0">
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
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-0.5 font-mono">
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
                      className="p-1 rounded text-zinc-500 hover:text-white hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all shrink-0"
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

      {/* 6. Desktop System Footnote */}
      <div className="flex items-center justify-center gap-2 pt-2 text-xs text-zinc-500">
        <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
        <span>100% Offline & Private Local Indexing</span>
      </div>
    </div>
  );
};
