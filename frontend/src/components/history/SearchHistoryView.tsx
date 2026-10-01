import { Search, Trash2 } from 'lucide-react';
import { SearchHistoryItem } from '../../api/types';

interface SearchHistoryViewProps {
  history: SearchHistoryItem[];
  onSelectQuery: (query: string) => void;
  onClearHistory: () => void;
}

export const SearchHistoryView: React.FC<SearchHistoryViewProps> = ({
  history,
  onSelectQuery,
  onClearHistory,
}) => {
  return (
    <div className="w-full max-w-4xl mx-auto space-y-6 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Recent Searches</h2>
          <p className="text-xs text-zinc-400 mt-1">
            Privacy-preserving local query history stored offline.
          </p>
        </div>
        {history.length > 0 && (
          <button
            type="button"
            onClick={onClearHistory}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.05] hover:bg-rose-500/10 text-zinc-400 hover:text-rose-300 border border-white/[0.08] hover:border-rose-500/20 text-xs font-medium transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear History</span>
          </button>
        )}
      </div>

      <div className="space-y-2">
        {history.map((item) => (
          <div
            key={item.id}
            onClick={() => onSelectQuery(item.query)}
            className="flex items-center justify-between p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.07] hover:border-white/15 cursor-pointer transition-all duration-150 select-none group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-2 rounded-xl bg-white/[0.04] text-zinc-400 group-hover:text-sky-300 transition-colors">
                <Search className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <span className="font-semibold text-white text-sm block truncate group-hover:text-sky-300 transition-colors">
                  {item.query}
                </span>
                <span className="text-[11px] text-zinc-500 block">
                  {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <span className="text-xs font-mono text-zinc-400 bg-white/[0.04] px-2 py-0.5 rounded-md border border-white/[0.06]">
                {item.result_count} results
              </span>
              {item.latency_ms > 0 && (
                <span className="text-[11px] font-mono text-zinc-500">
                  {item.latency_ms}ms
                </span>
              )}
            </div>
          </div>
        ))}

        {history.length === 0 && (
          <div className="p-12 text-center text-zinc-500 text-xs rounded-2xl bg-white/[0.01] border border-white/[0.04]">
            No search history yet. Searches you perform will appear here.
          </div>
        )}
      </div>
    </div>
  );
};
