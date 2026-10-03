import React, { useRef, useEffect } from 'react';
import { Search, X, Loader2, Sparkles } from 'lucide-react';

interface SearchBarProps {
  query: string;
  onChange: (query: string) => void;
  onSearch: (query: string) => void;
  isLoading: boolean;
  activeFilterCount?: number;
  autoFocus?: boolean;
  placeholder?: string;
  variant?: 'island' | 'glass';
}

export const SearchBar: React.FC<SearchBarProps> = ({
  query,
  onChange,
  onSearch,
  isLoading,
  activeFilterCount = 0,
  autoFocus = false,
  placeholder = 'Search what you want over here...',
  variant = 'island',
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
      {variant === 'island' ? (
        <div className="relative flex items-center w-full rounded-3xl bg-gradient-to-r from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] border border-white/50 shadow-[0_16px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl transition-all duration-200 focus-within:shadow-[0_20px_50px_rgba(0,0,0,0.6)] p-1.5 sm:p-2">
          {/* Left Search Icon */}
          <div className="flex items-center justify-center pl-4 pr-2 text-zinc-700">
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin text-black" />
            ) : (
              <Search className="w-5 h-5 text-zinc-700" />
            )}
          </div>

          {/* Input */}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full py-2.5 sm:py-3 text-sm sm:text-base font-medium text-black placeholder:text-zinc-500 bg-transparent border-none outline-none tracking-normal"
          />

          {/* Right Section: Active Filters + Clear + Search Action Button */}
          <div className="flex items-center gap-2 pr-1 text-xs">
            {activeFilterCount > 0 && (
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-black text-white font-medium text-[11px] shadow-sm">
                <Sparkles className="w-3 h-3 text-sky-300" />
                {activeFilterCount}
              </span>
            )}

            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1.5 rounded-full text-zinc-600 hover:text-black hover:bg-black/10 transition-colors"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              type="submit"
              className="flex items-center gap-1.5 px-4 py-2 sm:py-2.5 rounded-2xl bg-black hover:bg-zinc-800 text-white font-semibold text-xs sm:text-sm shadow-md transition-all active:scale-95"
            >
              <span>Search</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="relative flex items-center w-full rounded-2xl bg-[#14161b]/80 border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-xl transition-all duration-200 focus-within:border-white/30 focus-within:bg-[#181a20]/95 focus-within:shadow-[0_12px_40px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.15)]">
          {/* Left Search Icon */}
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
            placeholder={placeholder}
            className="w-full py-3.5 text-sm font-normal text-white placeholder-zinc-500 bg-transparent border-none outline-none tracking-normal"
          />

          {/* Right Section */}
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
      )}
    </form>
  );
};
