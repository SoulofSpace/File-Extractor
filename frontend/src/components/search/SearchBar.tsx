import React, { useRef, useEffect } from 'react';
import { Search, X, Loader2, Sparkles } from 'lucide-react';

interface SearchBarProps {
  query: string;
  onChange: (query: string) => void;
  onSearch: (query: string) => void;
  isLoading: boolean;
  activeFilterCount?: number;
  autoFocus?: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  query,
  onChange,
  onSearch,
  isLoading,
  activeFilterCount = 0,
  autoFocus = false,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Global Ctrl+K shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  const handleClear = () => {
    onChange('');
    inputRef.current?.focus();
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-full max-w-3xl mx-auto">
      <div className="relative flex items-center w-full rounded-2xl bg-[#14161b]/80 border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-xl transition-all duration-200 focus-within:border-white/30 focus-within:bg-[#181a20]/95 focus-within:shadow-[0_12px_40px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.15)]">
        {/* Left Search Icon / Sparkle */}
        <div className="flex items-center justify-center pl-5 pr-2 text-zinc-400">
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-sky-400" />
          ) : (
            <Search className="w-5 h-5 text-zinc-400" />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Search images, documents, people, objects, text and more..."
          className="w-full py-4 text-[15px] font-normal text-white placeholder-zinc-500 bg-transparent border-none outline-none tracking-normal"
        />

        {/* Right Section: Active Filters + Clear + Keyboard Shortcut */}
        <div className="flex items-center gap-2 pr-4 text-xs">
          {activeFilterCount > 0 && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/25 font-medium text-[11px]">
              <Sparkles className="w-3 h-3" />
              {activeFilterCount} active
            </span>
          )}

          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          <div className="hidden sm:flex items-center gap-0.5 px-2 py-1 rounded-md bg-white/[0.06] border border-white/[0.08] text-zinc-400 font-mono text-[11px] tracking-wider pointer-events-none">
            <span>Ctrl</span>
            <span>K</span>
          </div>
        </div>
      </div>
    </form>
  );
};
