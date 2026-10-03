import React from 'react';
import { FolderSync, ShieldCheck } from 'lucide-react';
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
  if (!showCompactSearch) return null;

  return (
    <header className="w-full rounded-3xl bg-gradient-to-r from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] border border-white/60 shadow-[0_12px_30px_rgba(0,0,0,0.5)] px-4 py-2 flex items-center justify-between gap-4 z-20 select-none text-black shrink-0">
      {/* Center Search Input */}
      <div className="flex-1 max-w-2xl">
        <SearchBar
          query={query}
          onChange={onQueryChange}
          onSearch={onSearch}
          isLoading={isLoading}
          activeFilterCount={activeFilterCount}
          variant="island"
          placeholder="Search what you want over here..."
        />
      </div>

      {/* Right System Indicators */}
      <div className="flex items-center gap-2.5 text-xs">
        {isScanning ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-2xl bg-black text-sky-300 font-medium animate-pulse shadow-sm font-mono">
            <FolderSync className="w-3.5 h-3.5 animate-spin" />
            <span>Scanning...</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-black text-white font-mono shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>{totalFiles.toLocaleString()} files</span>
          </div>
        )}

        <div
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-black/80 text-white text-[11px] font-medium shadow-sm"
          title="100% Offline Local Privacy"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Offline</span>
        </div>
      </div>
    </header>
  );
};
