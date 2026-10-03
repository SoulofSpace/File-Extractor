import React from 'react';
import {
  Home,
  Files,
  Image,
  FileText,
  Film,
  Music,
  Code2,
  Archive,
  History,
  Bookmark,
  FolderSync,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export type NavItemKey =
  | 'home'
  | 'all'
  | 'images'
  | 'documents'
  | 'videos'
  | 'audio'
  | 'code'
  | 'archives'
  | 'recent_searches'
  | 'saved_searches'
  | 'indexing'
  | 'settings';

interface SidebarProps {
  activeNav: NavItemKey;
  onSelectNav: (key: NavItemKey) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  totalIndexedFiles: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  onSelectNav,
  isCollapsed,
  onToggleCollapse,
  totalIndexedFiles,
}) => {
  const mainNav = [
    { key: 'home', label: 'Home', icon: Home },
    { key: 'all', label: 'All Files', icon: Files },
  ];

  const categoryNav = [
    { key: 'images', label: 'Images', icon: Image },
    { key: 'documents', label: 'Documents', icon: FileText },
    { key: 'videos', label: 'Videos', icon: Film },
    { key: 'audio', label: 'Audio', icon: Music },
    { key: 'code', label: 'Code', icon: Code2 },
    { key: 'archives', label: 'Archives', icon: Archive },
  ];

  const toolsNav = [
    { key: 'recent_searches', label: 'Recent Searches', icon: History },
    { key: 'saved_searches', label: 'Saved Searches', icon: Bookmark },
    { key: 'indexing', label: 'Indexing & Folders', icon: FolderSync },
    { key: 'settings', label: 'Settings', icon: Settings },
  ];

  // Button style matching "Button style ref" from reference image
  const renderNavButton = (item: { key: string; label: string; icon: any }) => {
    const Icon = item.icon;
    const isActive = activeNav === item.key;

    return (
      <button
        key={item.key}
        type="button"
        onClick={() => onSelectNav(item.key as NavItemKey)}
        title={isCollapsed ? item.label : undefined}
        className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-xs transition-all duration-150 select-none group relative ${
          isActive
            ? 'bg-black text-white font-semibold shadow-lg ring-1 ring-black/40 scale-[1.02]'
            : 'bg-black/10 hover:bg-black text-zinc-900 hover:text-white font-medium hover:shadow-md'
        } ${isCollapsed ? 'justify-center px-0' : ''}`}
      >
        <Icon
          className={`w-4 h-4 shrink-0 transition-transform duration-150 group-hover:scale-110 ${
            isActive ? 'text-white' : 'text-zinc-800 group-hover:text-white'
          }`}
        />
        {!isCollapsed && <span className="truncate">{item.label}</span>}
      </button>
    );
  };

  return (
    <aside
      className={`h-full flex flex-col gap-3 select-none z-30 transition-all duration-200 ${
        isCollapsed ? 'w-20' : 'w-60'
      }`}
    >
      {/* 1. Top Island: Brand / Logo Card (Direct from Reference Image) */}
      <div className="w-full rounded-3xl bg-gradient-to-r from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] p-3.5 shadow-[0_12px_30px_rgba(0,0,0,0.5)] border border-white/60 flex items-center justify-between shrink-0">
        {!isCollapsed ? (
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center text-white font-black text-xs shadow-md shrink-0">
              X
            </div>
            <span className="font-extrabold tracking-wider text-xs text-black uppercase truncate">
              FILE XTRACTOR
            </span>
          </div>
        ) : (
          <div className="w-8 h-8 mx-auto rounded-full bg-black flex items-center justify-center text-white font-black text-xs shadow-md">
            X
          </div>
        )}

        <button
          type="button"
          onClick={onToggleCollapse}
          className={`p-1.5 rounded-full bg-black/10 hover:bg-black text-black hover:text-white transition-colors ${
            isCollapsed ? 'hidden' : 'block'
          }`}
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Main Sidebar Island: Navigation Card (Direct from Reference Image) */}
      <div className="flex-1 w-full rounded-3xl bg-gradient-to-b from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] p-3 shadow-[0_16px_40px_rgba(0,0,0,0.55)] border border-white/60 flex flex-col justify-between overflow-hidden">
        {/* Navigation Items Scroll Area */}
        <div className="space-y-4 overflow-y-auto pr-0.5">
          {/* Main Group */}
          <div className="space-y-1.5">{mainNav.map(renderNavButton)}</div>

          {/* Library Group */}
          <div>
            {!isCollapsed && (
              <span className="px-3 text-[10px] font-bold text-zinc-700 uppercase tracking-wider block mb-1.5 font-mono">
                Library
              </span>
            )}
            <div className="space-y-1">{categoryNav.map(renderNavButton)}</div>
          </div>

          {/* System Group */}
          <div>
            {!isCollapsed && (
              <span className="px-3 text-[10px] font-bold text-zinc-700 uppercase tracking-wider block mb-1.5 font-mono">
                System
              </span>
            )}
            <div className="space-y-1">{toolsNav.map(renderNavButton)}</div>
          </div>
        </div>

        {/* Bottom Island Status / Expand Button */}
        <div className="pt-2 border-t border-black/10 shrink-0">
          {isCollapsed ? (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="w-full flex justify-center p-2 rounded-2xl bg-black text-white hover:bg-zinc-800 transition-colors shadow-sm"
              title="Expand Sidebar"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <div className="flex items-center justify-between px-3 py-2 rounded-2xl bg-black text-white text-xs font-mono shadow-md">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[11px] font-medium">Ready</span>
              </div>
              <span className="text-[10px] text-zinc-400">{totalIndexedFiles} files</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
