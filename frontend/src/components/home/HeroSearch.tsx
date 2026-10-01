import React from 'react';
import { SearchBar } from '../search/SearchBar';
import { Sparkles, Image, FileText, History, Zap } from 'lucide-react';

interface HeroSearchProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSearch: (q: string) => void;
  isLoading: boolean;
  onQuickCategory: (cat: string) => void;
  onQuickRecentSearches: () => void;
}

export const HeroSearch: React.FC<HeroSearchProps> = ({
  query,
  onQueryChange,
  onSearch,
  isLoading,
  onQuickCategory,
  onQuickRecentSearches,
}) => {
  const exampleQueries = [
    'guy in blue dress',
    'guy in green shirt',
    'silver metal key',
    'yellow soccer jersey',
    'dog in grass',
    'DBMS DA 3 notes',
  ];

  return (
    <div className="relative z-10 flex flex-col items-center justify-center min-h-[75vh] px-4 py-8 text-center max-w-4xl mx-auto select-none">
      {/* Brand Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] backdrop-blur-md mb-6 shadow-sm">
        <Sparkles className="w-3.5 h-3.5 text-sky-400" />
        <span className="text-xs font-semibold tracking-wider text-zinc-300 uppercase">
          Local Multimodal Intelligence V3
        </span>
      </div>

      {/* Main Title & Tagline */}
      <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-4 leading-tight">
        Find Anything.{' '}
        <span className="bg-gradient-to-r from-sky-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
          Instantly.
        </span>
      </h1>

      <p className="text-sm sm:text-base text-zinc-400 max-w-xl mb-10 leading-relaxed">
        Search across your files using natural language, visual concepts, OCR text, and local AI reasoning.
      </p>

      {/* Large Hero Search Bar */}
      <div className="w-full mb-8">
        <SearchBar
          query={query}
          onChange={onQueryChange}
          onSearch={onSearch}
          isLoading={isLoading}
          autoFocus={true}
        />
      </div>

      {/* Quick Action Chips */}
      <div className="flex items-center justify-center gap-2.5 flex-wrap mb-8">
        <button
          type="button"
          onClick={() => onSearch('photo')}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] hover:border-white/20 text-xs font-medium text-zinc-300 hover:text-white backdrop-blur-md transition-all duration-150"
        >
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span>Search Everything</span>
        </button>
        <button
          type="button"
          onClick={() => onQuickCategory('IMAGE')}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] hover:border-white/20 text-xs font-medium text-zinc-300 hover:text-white backdrop-blur-md transition-all duration-150"
        >
          <Image className="w-3.5 h-3.5 text-sky-400" />
          <span>Images</span>
        </button>
        <button
          type="button"
          onClick={() => onQuickCategory('DOCUMENT')}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] hover:border-white/20 text-xs font-medium text-zinc-300 hover:text-white backdrop-blur-md transition-all duration-150"
        >
          <FileText className="w-3.5 h-3.5 text-emerald-400" />
          <span>Documents</span>
        </button>
        <button
          type="button"
          onClick={onQuickRecentSearches}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] hover:border-white/20 text-xs font-medium text-zinc-300 hover:text-white backdrop-blur-md transition-all duration-150"
        >
          <History className="w-3.5 h-3.5 text-purple-400" />
          <span>Recent Searches</span>
        </button>
      </div>

      {/* Suggested Prompts */}
      <div className="flex items-center justify-center gap-2 flex-wrap text-xs">
        <span className="text-zinc-500 font-medium">Try asking:</span>
        {exampleQueries.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              onQueryChange(ex);
              onSearch(ex);
            }}
            className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.05] text-zinc-400 hover:text-zinc-200 transition-colors font-mono text-[11px]"
          >
            "{ex}"
          </button>
        ))}
      </div>
    </div>
  );
};
