import React from 'react';
import { ArrowUpDown, LayoutGrid, List } from 'lucide-react';
import { CategoryFilterBar } from './CategoryFilterBar';
import { ActiveFilterChips } from './ActiveFilterChips';

interface SmartFilterSummaryProps {
  query: string;
  totalResults: number;
  elapsedMs: number;
  currentCategory: string;
  onSelectCategory: (categoryId: string) => void;
  selectedFormats: string[];
  onToggleFormat: (ext: string) => void;
  onSelectAllFormats: (exts: string[]) => void;
  onClearCategoryFormats: (exts: string[]) => void;
  onClearAllFilters: () => void;
  sortBy: string;
  onSortChange: (sort: 'relevance' | 'date_desc' | 'date_asc' | 'size_desc' | 'size_asc' | 'name') => void;
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  isVisualQuery?: boolean;
}

export const SmartFilterSummary: React.FC<SmartFilterSummaryProps> = ({
  query,
  totalResults,
  elapsedMs,
  currentCategory,
  onSelectCategory,
  selectedFormats,
  onToggleFormat,
  onSelectAllFormats,
  onClearCategoryFormats,
  onClearAllFilters,
  sortBy,
  onSortChange,
  viewMode,
  onViewModeChange,
  isVisualQuery = false,
}) => {
  return (
    <div className="relative z-40 w-full max-w-6xl mx-auto px-4 py-3 space-y-2.5 bg-[#121318]/90 border border-white/[0.08] rounded-2xl backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
      {/* Top Row: Query Context + Search Mode Badge + Result Count + Controls */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {/* Left: Query & Mode info */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <span className="text-zinc-500 font-medium">
              {query === '*' || !query ? 'Browsing:' : 'Search:'}
            </span>
            <span className="font-semibold text-white truncate max-w-xs">
              {query === '*' || !query
                ? currentCategory === 'ALL'
                  ? 'All Files'
                  : currentCategory.charAt(0) + currentCategory.slice(1).toLowerCase()
                : query}
            </span>
          </div>

          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/[0.05] text-zinc-300 border border-white/[0.1] text-[11px] font-medium tracking-wide">
            {query === '*' || !query
              ? 'Library Browse'
              : isVisualQuery
              ? 'Visual Search'
              : 'Indexed Search'}
          </span>

          <span className="text-xs font-mono font-medium text-zinc-400 bg-white/[0.04] px-2.5 py-0.5 rounded-full border border-white/[0.06]">
            {totalResults.toLocaleString()} results
            {elapsedMs > 0 && <span className="text-zinc-500 ml-1.5">({elapsedMs.toFixed(0)}ms)</span>}
          </span>
        </div>

        {/* Right: Sort By + View Mode Toggle */}
        <div className="flex items-center gap-2 text-xs">
          {/* Sort By Dropdown */}
          <div className="flex items-center gap-1.5 bg-white/[0.04] border border-white/[0.08] rounded-xl px-2.5 py-1.5 text-zinc-300 hover:border-white/20 transition-colors">
            <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400" />
            <span className="text-zinc-500">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as any)}
              className="bg-transparent text-white font-medium outline-none cursor-pointer text-xs pr-1"
            >
              <option value="relevance" className="bg-[#181a20] text-white">Relevance</option>
              <option value="date_desc" className="bg-[#181a20] text-white">Newest First</option>
              <option value="date_asc" className="bg-[#181a20] text-white">Oldest First</option>
              <option value="size_desc" className="bg-[#181a20] text-white">Largest Size</option>
              <option value="size_asc" className="bg-[#181a20] text-white">Smallest Size</option>
              <option value="name" className="bg-[#181a20] text-white">Filename A-Z</option>
            </select>
          </div>

          {/* Grid / List View Toggle Buttons */}
          <div className="flex items-center p-0.5 rounded-xl bg-white/[0.04] border border-white/[0.08]">
            <button
              type="button"
              onClick={() => onViewModeChange('grid')}
              className={`p-1.5 rounded-lg transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white/20 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Grid View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange('list')}
              className={`p-1.5 rounded-lg transition-colors ${
                viewMode === 'list'
                  ? 'bg-white/20 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="List View"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Middle Row: Primary Category Filter Buttons with Dropdowns */}
      <div className="pt-1 border-t border-white/[0.06] relative z-40">
        <CategoryFilterBar
          currentCategory={currentCategory}
          onSelectCategory={onSelectCategory}
          selectedFormats={selectedFormats}
          onToggleFormat={onToggleFormat}
          onSelectAllFormats={onSelectAllFormats}
          onClearCategoryFormats={onClearCategoryFormats}
        />
      </div>

      {/* Bottom Row: Active Filter Chips */}
      <ActiveFilterChips
        currentCategory={currentCategory}
        onResetCategory={() => onSelectCategory('ALL')}
        selectedFormats={selectedFormats}
        onRemoveFormat={onToggleFormat}
        onClearAll={onClearAllFilters}
      />
    </div>
  );
};
