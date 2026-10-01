import React from 'react';
import { Sparkles, FolderSync, ShieldCheck } from 'lucide-react';
import { SearchBar } from '../search/SearchBar';

interface TopBarProps {
  showCompactSearch: boolean;
  query: string;
  onQueryChange: (q: string) => void;
  onSearch: (q: string) => void;
  isLoading: boolean;
  activeFilterCount: number;
  totalFiles: number;
  isScanning: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  showCompactSearch,
  query,
  onQueryChange,
  onSearch,
  isLoading,
  activeFilterCount,
  totalFiles,
  isScanning,
}) => {
  return (
    <header className="h-16 px-6 border-b border-white/[0.06] bg-[#0b0c0e]/80 backdrop-blur-xl flex items-center justify-between gap-4 z-20 select-none">
      {/* Center Search Input (Shown when user has navigated past Hero Home) */}
      <div className="flex-1 max-w-2xl">
        {showCompactSearch ? (
          <SearchBar
            query={query}
            onChange={onQueryChange}
            onSearch={onSearch}
            isLoading={isLoading}
            activeFilterCount={activeFilterCount}
          />
        ) : (
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-400">
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span className="tracking-wide">AI-POWERED LOCAL RETRIEVAL</span>
          </div>
        )}
      </div>

      {/* Right System Indicators */}
      <div className="flex items-center gap-3 text-xs">
        {isScanning ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/25 text-sky-300 font-medium animate-pulse">
            <FolderSync className="w-3.5 h-3.5 animate-spin" />
            <span>Scanning...</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="font-mono">{totalFiles.toLocaleString()} files ready</span>
          </div>
        )}

        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06] text-zinc-400 text-[11px]" title="100% Offline Local Privacy">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Offline</span>
        </div>
      </div>
    </header>
  );
};
