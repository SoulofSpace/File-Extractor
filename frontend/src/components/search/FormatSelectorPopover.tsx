import React, { useRef, useEffect } from 'react';
import { Check, X } from 'lucide-react';
import { CategoryConfig } from '../../config/categories';

interface FormatSelectorPopoverProps {
  category: CategoryConfig;
  selectedFormats: string[];
  onToggleFormat: (ext: string) => void;
  onSelectAll: (exts: string[]) => void;
  onClearCategory: (exts: string[]) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const FormatSelectorPopover: React.FC<FormatSelectorPopoverProps> = ({
  category,
  selectedFormats,
  onToggleFormat,
  onSelectAll,
  onClearCategory,
  isOpen,
  onClose,
}) => {
  const popoverRef = useRef<HTMLDivElement | null>(null);

  // Outside click & Escape listener
  useEffect(() => {
    if (!isOpen) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !category.formats) return null;

  const allCategoryExts = category.formats.map((f) => f.ext.toLowerCase());
  const activeCount = allCategoryExts.filter((ext) => selectedFormats.includes(ext)).length;
  const isAllSelected = activeCount === allCategoryExts.length && allCategoryExts.length > 0;

  return (
    <div
      ref={popoverRef}
      className="absolute top-full left-0 mt-2 w-64 rounded-2xl bg-[#14151a]/95 border border-white/10 shadow-[0_16px_48px_rgba(0,0,0,0.6)] backdrop-blur-2xl z-50 overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150"
    >
      {/* Popover Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08] bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white tracking-wide uppercase">
            {category.label}
          </span>
          {activeCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-sky-500/20 text-sky-300 font-mono text-[10px]">
              {activeCount}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-white p-1 rounded-md hover:bg-white/10 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Scrollable Format Checkbox List */}
      <div className="max-h-60 overflow-y-auto px-2 py-2 space-y-0.5">
        {category.formats.map((fmt) => {
          const isSelected = selectedFormats.includes(fmt.ext.toLowerCase());
          return (
            <label
              key={fmt.ext}
              onClick={() => onToggleFormat(fmt.ext.toLowerCase())}
              className="flex items-center justify-between px-3 py-2 rounded-xl hover:bg-white/[0.06] cursor-pointer transition-colors group select-none"
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={`w-4 h-4 rounded-md border flex items-center justify-center transition-all ${
                    isSelected
                      ? 'bg-sky-500 border-sky-400 text-black'
                      : 'border-white/20 bg-white/[0.03] group-hover:border-white/40'
                  }`}
                >
                  {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                </div>
                <span className="text-xs font-medium text-zinc-200 group-hover:text-white">
                  {fmt.label}
                </span>
              </div>
              <span className="text-[10px] font-mono text-zinc-500 group-hover:text-zinc-400">
                .{fmt.ext}
              </span>
            </label>
          );
        })}
      </div>

      {/* Popover Footer: Select All / Clear */}
      <div className="flex items-center justify-between px-3 py-2.5 border-t border-white/[0.08] bg-white/[0.02] text-xs">
        <button
          type="button"
          onClick={() => (isAllSelected ? onClearCategory(allCategoryExts) : onSelectAll(allCategoryExts))}
          className="text-xs font-medium text-sky-400 hover:text-sky-300 px-2 py-1 rounded hover:bg-sky-500/10 transition-colors"
        >
          {isAllSelected ? 'Deselect All' : 'Select All'}
        </button>
        {activeCount > 0 && (
          <button
            type="button"
            onClick={() => onClearCategory(allCategoryExts)}
            className="text-xs font-medium text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-white/10 transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
};
