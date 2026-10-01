import React from 'react';
import { X, RotateCcw } from 'lucide-react';

interface ActiveFilterChipsProps {
  currentCategory: string;
  onResetCategory: () => void;
  selectedFormats: string[];
  onRemoveFormat: (ext: string) => void;
  onClearAll: () => void;
}

export const ActiveFilterChips: React.FC<ActiveFilterChipsProps> = ({
  currentCategory,
  onResetCategory,
  selectedFormats,
  onRemoveFormat,
  onClearAll,
}) => {
  const hasCategoryFilter = currentCategory.toUpperCase() !== 'ALL';
  const hasFormatFilters = selectedFormats.length > 0;

  if (!hasCategoryFilter && !hasFormatFilters) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap pt-2 text-xs">
      <span className="text-zinc-500 font-medium">Active:</span>

      {/* Category chip */}
      {hasCategoryFilter && (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/10 text-white border border-white/15 text-xs font-medium backdrop-blur-md">
          <span>{currentCategory}</span>
          <button
            type="button"
            onClick={onResetCategory}
            className="text-zinc-400 hover:text-white p-0.5 rounded hover:bg-white/10 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      )}

      {/* Format extension chips */}
      {selectedFormats.map((ext) => (
        <span
          key={ext}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-500/15 text-sky-200 border border-sky-500/25 text-xs font-mono font-medium backdrop-blur-md"
        >
          <span>.{ext.toUpperCase()}</span>
          <button
            type="button"
            onClick={() => onRemoveFormat(ext)}
            className="text-sky-300 hover:text-white p-0.5 rounded hover:bg-white/10 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}

      {/* Clear all button */}
      <button
        type="button"
        onClick={onClearAll}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-white/5 transition-colors font-medium text-xs"
      >
        <RotateCcw className="w-3 h-3" />
        <span>Clear all</span>
      </button>
    </div>
  );
};
