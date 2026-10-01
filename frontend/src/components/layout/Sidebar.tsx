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
  HardDrive
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

  const renderNavButton = (item: { key: string; label: string; icon: any }) => {
    const Icon = item.icon;
    const isActive = activeNav === item.key;

    return (
      <button
        key={item.key}
        type="button"
        onClick={() => onSelectNav(item.key as NavItemKey)}
        title={isCollapsed ? item.label : undefined}
        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all duration-150 select-none group relative ${
          isActive
            ? 'bg-white/10 text-white font-semibold shadow-sm border border-white/10'
            : 'text-zinc-400 hover:text-white hover:bg-white/[0.04]'
        }`}
      >
        {/* Active Pill Indicator */}
        {isActive && (
          <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
        )}
        <Icon className={`w-4 h-4 shrink-0 transition-transform duration-150 group-hover:scale-110 ${isActive ? 'text-sky-300' : 'text-zinc-400 group-hover:text-white'}`} />
        {!isCollapsed && <span className="truncate">{item.label}</span>}
      </button>
    );
  };

  return (
    <aside
      className={`h-full flex flex-col justify-between bg-[#0e1014]/90 border-r border-white/[0.08] backdrop-blur-xl z-30 transition-all duration-200 select-none ${
        isCollapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Top Branding & Collapse Control */}
      <div>
        <div className="flex items-center justify-between px-4 py-4 border-b border-white/[0.06]">
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white font-black text-xs shadow-md">
                X
              </div>
              <span className="font-extrabold tracking-wider text-xs text-white uppercase">
                FILE XTRACTOR
              </span>
            </div>
          )}

          {isCollapsed && (
            <div className="w-8 h-8 mx-auto rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md">
              X
            </div>
          )}

          <button
            type="button"
            onClick={onToggleCollapse}
            className={`p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors ${
              isCollapsed ? 'hidden' : 'block'
            }`}
            title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation Groups */}
        <div className="p-3 space-y-5 overflow-y-auto max-h-[calc(100vh-140px)]">
          {/* Main items */}
          <div className="space-y-1">
            {mainNav.map(renderNavButton)}
          </div>

          {/* Categories */}
          <div>
            {!isCollapsed && (
              <span className="px-3 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">
                Library
              </span>
            )}
            <div className="space-y-0.5">
              {categoryNav.map(renderNavButton)}
            </div>
          </div>

          {/* Tools & System */}
          <div>
            {!isCollapsed && (
              <span className="px-3 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">
                System
              </span>
            )}
            <div className="space-y-0.5">
              {toolsNav.map(renderNavButton)}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Summary Bar */}
      <div className="p-3 border-t border-white/[0.06] bg-white/[0.01]">
        {isCollapsed ? (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="w-full flex justify-center p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Expand Sidebar"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <div className="flex items-center justify-between px-2 py-1.5 text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <HardDrive className="w-3.5 h-3.5 text-sky-400" />
              <span>{totalIndexedFiles.toLocaleString()} files indexed</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
