import { Bookmark, Trash2, ArrowRight } from 'lucide-react';
import { SavedSearchItem } from '../../api/types';

interface SavedSearchesViewProps {
  savedSearches: SavedSearchItem[];
  onSelectQuery: (query: string) => void;
  onDeleteSavedSearch: (id: number) => void;
}

export const SavedSearchesView: React.FC<SavedSearchesViewProps> = ({
  savedSearches,
  onSelectQuery,
  onDeleteSavedSearch,
}) => {
  return (
    <div className="w-full max-w-4xl mx-auto space-y-6 p-4">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Saved Searches</h2>
        <p className="text-xs text-zinc-400 mt-1">
          Quickly access your pinned queries and custom file collections.
        </p>
      </div>

      <div className="space-y-2">
        {savedSearches.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-colors group select-none"
          >
            <div
              onClick={() => onSelectQuery(item.query)}
              className="flex items-center gap-3.5 min-w-0 cursor-pointer flex-1"
            >
              <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-300 border border-purple-500/20 group-hover:scale-105 transition-transform">
                <Bookmark className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <span className="font-semibold text-white text-sm block truncate group-hover:text-purple-300 transition-colors">
                  {item.name || item.query}
                </span>
                <span className="text-xs text-zinc-400 font-mono block truncate">
                  "{item.query}"
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => onSelectQuery(item.query)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white/[0.08] hover:bg-white text-zinc-200 hover:text-zinc-950 font-bold text-xs transition-colors"
              >
                <span>Run</span>
                <ArrowRight className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={() => onDeleteSavedSearch(item.id)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                title="Delete saved search"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}

        {savedSearches.length === 0 && (
          <div className="p-12 text-center text-zinc-500 text-xs rounded-2xl bg-white/[0.01] border border-white/[0.04]">
            No saved searches yet. Click the bookmark icon on any search result to pin it here.
          </div>
        )}
      </div>
    </div>
  );
};
