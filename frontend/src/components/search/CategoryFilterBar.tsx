import React, { useState } from 'react';
import { ChevronDown, LayoutGrid, FileText, Image, Film, Music, Code2, Archive } from 'lucide-react';
import { CATEGORIES_CONFIG } from '../../config/categories';
import { FormatSelectorPopover } from './FormatSelectorPopover';

interface CategoryFilterBarProps {
  currentCategory: string;
  onSelectCategory: (categoryId: string) => void;
  selectedFormats: string[];
  onToggleFormat: (ext: string) => void;
  onSelectAllFormats: (exts: string[]) => void;
  onClearCategoryFormats: (exts: string[]) => void;
}

export const CategoryFilterBar: React.FC<CategoryFilterBarProps> = ({
  currentCategory,
  onSelectCategory,
  selectedFormats,
  onToggleFormat,
  onSelectAllFormats,
  onClearCategoryFormats,
}) => {
  const [openPopoverId, setOpenPopoverId] = useState<string | null>(null);

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'LayoutGrid':
        return <LayoutGrid className="w-3.5 h-3.5" />;
      case 'FileText':
        return <FileText className="w-3.5 h-3.5" />;
      case 'Image':
        return <Image className="w-3.5 h-3.5" />;
      case 'Film':
        return <Film className="w-3.5 h-3.5" />;
      case 'Music':
        return <Music className="w-3.5 h-3.5" />;
      case 'Code2':
        return <Code2 className="w-3.5 h-3.5" />;
      case 'Archive':
        return <Archive className="w-3.5 h-3.5" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {CATEGORIES_CONFIG.map((cat) => {
        const isCurrent = currentCategory.toUpperCase() === cat.id.toUpperCase();
        const catFormats = cat.formats?.map((f) => f.ext.toLowerCase()) || [];
        const activeSubFormats = catFormats.filter((ext) => selectedFormats.includes(ext));
        const hasActiveSub = activeSubFormats.length > 0;
        const isPopoverOpen = openPopoverId === cat.id;

        return (
          <div key={cat.id} className="relative">
            <div
              className={`flex items-center rounded-xl text-xs font-medium border transition-all duration-150 ${
                isCurrent || hasActiveSub
                  ? 'bg-white/15 text-white border-white/30 shadow-[0_2px_12px_rgba(255,255,255,0.06)]'
                  : 'bg-white/[0.04] text-zinc-300 border-white/[0.08] hover:bg-white/[0.08] hover:text-white'
              }`}
            >
              {/* Category Main Button */}
              <button
                type="button"
                onClick={() => {
                  onSelectCategory(cat.id);
                  setOpenPopoverId(null);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5"
              >
                {getIcon(cat.iconName)}
                <span>{cat.label}</span>
                {hasActiveSub && (
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
                )}
              </button>

              {/* Expandable Dropdown Arrow (if category has sub-formats) */}
              {cat.hasFormats && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenPopoverId(isPopoverOpen ? null : cat.id);
                  }}
                  className={`px-1.5 py-1.5 border-l border-white/[0.08] hover:bg-white/10 transition-colors ${
                    isPopoverOpen ? 'bg-white/15 text-sky-300' : 'text-zinc-400 hover:text-white'
                  }`}
                  title={`Filter ${cat.label} extensions`}
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Popover */}
            {cat.hasFormats && (
              <FormatSelectorPopover
                category={cat}
                selectedFormats={selectedFormats}
                onToggleFormat={onToggleFormat}
                onSelectAll={onSelectAllFormats}
                onClearCategory={onClearCategoryFormats}
                isOpen={isPopoverOpen}
                onClose={() => setOpenPopoverId(null)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
