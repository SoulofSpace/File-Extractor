import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar, NavItemKey } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { InteractiveGradientBackground } from './components/background/InteractiveGradientBackground';
import { HeroSearch } from './components/home/HeroSearch';
import { SmartFilterSummary } from './components/search/SmartFilterSummary';
import { FileGrid } from './components/results/FileGrid';
import { FileList } from './components/results/FileList';
import { PreviewDrawer } from './components/preview/PreviewDrawer';
import { FolderManager } from './components/indexing/FolderManager';
import { SearchHistoryView } from './components/history/SearchHistoryView';
import { SavedSearchesView } from './components/history/SavedSearchesView';
import { SettingsDialog } from './components/settings/SettingsDialog';
import { apiClient } from './api/client';
import {
  SearchResultItem,
  SystemStatus,
  FolderItem,
  SearchHistoryItem,
  SavedSearchItem,
  IndexingStatus
} from './api/types';
import { Loader2, FileQuestion } from 'lucide-react';
import { ErrorBoundary } from './components/common/ErrorBoundary';

export const App: React.FC = () => {
  // Navigation State
  const [activeNav, setActiveNav] = useState<NavItemKey>('home');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [currentCategory, setCurrentCategory] = useState<string>('ALL');
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<'relevance' | 'date_desc' | 'date_asc' | 'size_desc' | 'size_asc' | 'name'>('relevance');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Results & UI State
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [isVisualQuery, setIsVisualQuery] = useState(false);
  const [selectedFile, setSelectedFile] = useState<SearchResultItem | null>(null);

  // Data & Background System States
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearchItem[]>([]);
  const [recentFiles, setRecentFiles] = useState<SearchResultItem[]>([]);
  const [indexingStatus, setIndexingStatus] = useState<IndexingStatus>({
    is_scanning: false,
    current_folder: '',
    current_file: '',
    current_count: 0,
    total_count: 0,
    failures: 0,
  });

  // Settings: interactive gradient background enabled by default
  const [animationEnabled, setAnimationEnabled] = useState(true);

  // Load Initial Data
  const refreshSystemData = useCallback(async () => {
    try {
      const [status, folderList, hist, saved, recent] = await Promise.all([
        apiClient.getStatus(),
        apiClient.getFolders(),
        apiClient.getSearchHistory(40),
        apiClient.getSavedSearches(),
        apiClient.getRecentFiles(12),
      ]);
      setSystemStatus(status);
      setFolders(folderList);
      setHistory(hist);
      setSavedSearches(saved);
      setRecentFiles(recent || []);
      if (status.indexing) {
        setIndexingStatus(status.indexing);
      }
    } catch (err) {
      console.error('Failed to load system data from backend:', err);
    }
  }, []);

  useEffect(() => {
    refreshSystemData();
    // Poll indexing status every 3 seconds
    const interval = setInterval(async () => {
      try {
        const idx = await apiClient.getIndexingStatus();
        setIndexingStatus(idx);
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshSystemData]);

  // Execute Search
  const handleExecuteSearch = useCallback(
    async (
      queryToSearch: string,
      category = currentCategory,
      formats = selectedFormats,
      sort = sortBy,
      targetNav?: NavItemKey
    ) => {
      const q = queryToSearch.trim();
      if (!q) return;

      setIsSearching(true);
      setSubmittedQuery(q);

      if (targetNav) {
        setActiveNav(targetNav);
      } else if (category && category !== 'ALL') {
        const navMap: Record<string, NavItemKey> = {
          IMAGE: 'images',
          DOCUMENT: 'documents',
          VIDEO: 'videos',
          AUDIO: 'audio',
          CODE: 'code',
          ARCHIVE: 'archives',
        };
        setActiveNav(navMap[category.toUpperCase()] || 'all');
      } else {
        setActiveNav('all');
      }

      try {
        const response = await apiClient.search({
          query: q,
          category,
          formats,
          sort_by: sort,
          limit: 100,
          save_history: q !== '*',
        });

        const rawList = Array.isArray(response?.results) ? response.results : [];
        const safeResults: SearchResultItem[] = rawList.map((r: any) => ({
          ...r,
          file_id: r.file_id || r.id || 0,
          filename: r.filename || 'Untitled',
          extension: (r.extension || '').toLowerCase(),
          category: r.category || r.file_type || 'File',
          size_bytes: Number(r.size_bytes || 0),
          relevance_score: Number(r.relevance_score || 0),
          match_evidence: r.match_evidence || {},
        }));

        setResults(safeResults);
        setTotalResults(Number(response?.total_results || safeResults.length));
        setElapsedMs(Number(response?.elapsed_ms || 0));
        setIsVisualQuery(Boolean(response?.query_plan?.is_visual));

        // Preserve selected file if present in new results
        if (selectedFile) {
          const match = safeResults.find((r) => r.file_id === selectedFile.file_id);
          setSelectedFile(match || null);
        }
      } catch (err) {
        console.error('Search request failed:', err);
        setResults([]);
        setTotalResults(0);
      } finally {
        setIsSearching(false);
      }
    },
    [currentCategory, selectedFormats, sortBy, selectedFile]
  );

  // Category change handler
  const handleCategorySelect = (catId: string) => {
    setCurrentCategory(catId);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, catId, selectedFormats, sortBy);
  };

  // Format toggle handler
  const handleToggleFormat = (ext: string) => {
    const nextFormats = selectedFormats.includes(ext)
      ? selectedFormats.filter((f) => f !== ext)
      : [...selectedFormats, ext];
    setSelectedFormats(nextFormats);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, currentCategory, nextFormats, sortBy);
  };

  const handleSelectAllFormats = (exts: string[]) => {
    const combined = Array.from(new Set([...selectedFormats, ...exts]));
    setSelectedFormats(combined);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, currentCategory, combined, sortBy);
  };

  const handleClearCategoryFormats = (exts: string[]) => {
    const filtered = selectedFormats.filter((f) => !exts.includes(f));
    setSelectedFormats(filtered);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, currentCategory, filtered, sortBy);
  };

  const handleClearAllFilters = () => {
    setCurrentCategory('ALL');
    setSelectedFormats([]);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, 'ALL', [], sortBy);
  };

  const handleSortChange = (
    newSort: 'relevance' | 'date_desc' | 'date_asc' | 'size_desc' | 'size_asc' | 'name'
  ) => {
    setSortBy(newSort);
    const q = submittedQuery || '*';
    handleExecuteSearch(q, currentCategory, selectedFormats, newSort);
  };

  // Open File
  const handleOpenFile = async (path: string, reveal = false) => {
    try {
      await apiClient.openFile(path, reveal);
    } catch (err) {
      console.error('Failed to open file:', err);
    }
  };

  // Sidebar navigation selection
  const handleSelectNav = (key: NavItemKey) => {
    setActiveNav(key);
    setSelectedFile(null);

    if (key === 'home') {
      setSearchQuery('');
      setSubmittedQuery('');
      setCurrentCategory('ALL');
      setSelectedFormats([]);
      refreshSystemData();
      return;
    }

    // If selecting a category from the sidebar (Images, Documents, Videos, etc.)
    const categoryMapping: Partial<Record<NavItemKey, string>> = {
      images: 'IMAGE',
      documents: 'DOCUMENT',
      videos: 'VIDEO',
      audio: 'AUDIO',
      code: 'CODE',
      archives: 'ARCHIVE',
      all: 'ALL',
    };

    if (categoryMapping[key]) {
      const cat = categoryMapping[key]!;
      setCurrentCategory(cat);
      if (submittedQuery && submittedQuery !== '*') {
        handleExecuteSearch(submittedQuery, cat, selectedFormats, sortBy, key);
      } else {
        // Run broad category browse
        handleExecuteSearch('*', cat, [], sortBy, key);
      }
    }
  };

  // Folder Actions
  const handleAddFolder = async (path: string) => {
    await apiClient.addFolder(path);
    refreshSystemData();
  };

  const handleRemoveFolder = async (path: string) => {
    await apiClient.removeFolder(path);
    refreshSystemData();
  };

  const handleRescanFolder = async (path: string) => {
    await apiClient.triggerRescan(path);
    refreshSystemData();
  };

  // History & Saved Searches Actions
  const handleClearHistory = async () => {
    await apiClient.clearSearchHistory();
    setHistory([]);
  };

  const handleDeleteSavedSearch = async (id: number) => {
    await apiClient.deleteSavedSearch(id);
    setSavedSearches((prev) => prev.filter((s) => s.id !== id));
  };

  // Check if we are on Home page
  const isHomePage = activeNav === 'home';

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-black text-[#f4f4f5] p-3 sm:p-4 gap-3 sm:gap-4 select-none">
      {/* 1. Interactive Gradient Background with smooth mouse reaction */}
      <InteractiveGradientBackground interactive={animationEnabled} />

      {/* 2. Main Desktop Sidebar: 2 Floating Islands + Black Pill Buttons */}
      <Sidebar
        activeNav={activeNav}
        onSelectNav={handleSelectNav}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        totalIndexedFiles={systemStatus?.total_files || 0}
      />

      {/* 3. Center Workspace Area */}
      <div className="relative flex-1 flex flex-col h-full min-w-0 z-10 overflow-hidden gap-3">
        {/* Top Floating Island Header (Shown when user has navigated past Hero Home) */}
        <TopBar
          showCompactSearch={!isHomePage}
          query={searchQuery}
          onQueryChange={setSearchQuery}
          onSearch={(q) => handleExecuteSearch(q)}
          isLoading={isSearching}
          activeFilterCount={(currentCategory !== 'ALL' ? 1 : 0) + selectedFormats.length}
          totalFiles={systemStatus?.total_files || 0}
          isScanning={indexingStatus.is_scanning}
        />

        {/* Dynamic Center Content View */}
        <main className="flex-1 overflow-y-auto px-1 py-1 flex flex-col min-h-0">
          {/* HOME SCREEN LANDING */}
          {isHomePage && (
            <HeroSearch
              query={searchQuery}
              onQueryChange={setSearchQuery}
              onSearch={(q) => handleExecuteSearch(q)}
              isLoading={isSearching}
              onSelectCategory={(cat) => {
                setCurrentCategory(cat);
                handleExecuteSearch('*', cat);
              }}
              categoryCounts={systemStatus?.category_counts}
              totalFiles={systemStatus?.total_files || 0}
              recentFiles={recentFiles}
              recentSearches={history.slice(0, 6).map((h) => h.query)}
              onOpenFile={handleOpenFile}
              onSelectFile={setSelectedFile}
            />
          )}

          {/* SEARCH RESULTS VIEW */}
          {(activeNav === 'all' ||
            ['images', 'documents', 'videos', 'audio', 'code', 'archives'].includes(activeNav)) && !isHomePage && (
              <div className="w-full flex-1 rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 flex flex-col gap-5 text-black overflow-y-auto">
                {/* Smart Filter Summary */}
                <SmartFilterSummary
                  query={submittedQuery}
                  totalResults={totalResults}
                  elapsedMs={elapsedMs}
                  currentCategory={currentCategory}
                  onSelectCategory={handleCategorySelect}
                  selectedFormats={selectedFormats}
                  onToggleFormat={handleToggleFormat}
                  onSelectAllFormats={handleSelectAllFormats}
                  onClearCategoryFormats={handleClearCategoryFormats}
                  onClearAllFilters={handleClearAllFilters}
                  sortBy={sortBy}
                  onSortChange={handleSortChange}
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                  isVisualQuery={isVisualQuery}
                />

                {/* Results Section */}
                <ErrorBoundary fallbackTitle="Results Rendering Error" onReset={handleClearAllFilters}>
                  {isSearching ? (
                    <div className="flex flex-col items-center justify-center p-24 text-center space-y-3 rounded-2xl bg-[#090a0f] text-white border border-white/10 shadow-lg">
                      <Loader2 className="w-8 h-8 animate-spin text-white" />
                      <span className="text-sm font-medium text-zinc-300">Searching your files with local AI...</span>
                    </div>
                  ) : results.length > 0 ? (
                    viewMode === 'grid' ? (
                      <FileGrid
                        files={results}
                        selectedFile={selectedFile}
                        onSelectFile={setSelectedFile}
                        onOpenFile={(p) => handleOpenFile(p)}
                      />
                    ) : (
                      <FileList
                        files={results}
                        selectedFile={selectedFile}
                        onSelectFile={setSelectedFile}
                        onOpenFile={(p) => handleOpenFile(p)}
                      />
                    )
                  ) : (
                    <div className="flex flex-col items-center justify-center p-20 text-center space-y-3 rounded-2xl bg-[#090a0f] text-white border border-white/10 shadow-lg">
                      <FileQuestion className="w-10 h-10 text-zinc-400" />
                      <h3 className="text-base font-semibold text-white">No files matched those filters</h3>
                      <p className="text-xs text-zinc-400 max-w-sm">
                        Try broadening your search query or clearing active format extensions.
                      </p>
                      <button
                        type="button"
                        onClick={handleClearAllFilters}
                        className="px-4 py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-colors mt-2 shadow-md"
                      >
                        Clear all filters
                      </button>
                    </div>
                  )}
                </ErrorBoundary>
              </div>
            )}

          {/* FOLDERS / INDEXING VIEW */}
          {activeNav === 'indexing' && (
            <div className="w-full flex-1 rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 flex flex-col text-black overflow-y-auto">
              <div className="bg-[#090a0f] text-white rounded-2xl p-6 shadow-xl border border-white/10">
                <FolderManager
                  folders={folders}
                  indexingStatus={indexingStatus}
                  onAddFolder={handleAddFolder}
                  onRemoveFolder={handleRemoveFolder}
                  onRescanFolder={handleRescanFolder}
                />
              </div>
            </div>
          )}

          {/* RECENT SEARCHES VIEW */}
          {activeNav === 'recent_searches' && (
            <div className="w-full flex-1 rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 flex flex-col text-black overflow-y-auto">
              <div className="bg-[#090a0f] text-white rounded-2xl p-6 shadow-xl border border-white/10">
                <SearchHistoryView
                  history={history}
                  onSelectQuery={(q) => {
                    setSearchQuery(q);
                    handleExecuteSearch(q);
                  }}
                  onClearHistory={handleClearHistory}
                />
              </div>
            </div>
          )}

          {/* SAVED SEARCHES VIEW */}
          {activeNav === 'saved_searches' && (
            <div className="w-full flex-1 rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 flex flex-col text-black overflow-y-auto">
              <div className="bg-[#090a0f] text-white rounded-2xl p-6 shadow-xl border border-white/10">
                <SavedSearchesView
                  savedSearches={savedSearches}
                  onSelectQuery={(q) => {
                    setSearchQuery(q);
                    handleExecuteSearch(q);
                  }}
                  onDeleteSavedSearch={handleDeleteSavedSearch}
                />
              </div>
            </div>
          )}

          {/* SETTINGS VIEW */}
          {activeNav === 'settings' && (
            <div className="w-full flex-1 rounded-3xl bg-gradient-to-br from-[#9ca3af] via-[#e2e8f0] to-[#ffffff] shadow-[0_24px_60px_rgba(0,0,0,0.65)] border border-white/60 p-5 sm:p-7 flex flex-col text-black overflow-y-auto">
              <div className="bg-[#090a0f] text-white rounded-2xl p-6 shadow-xl border border-white/10">
                <SettingsDialog
                  systemStatus={systemStatus}
                  animationEnabled={animationEnabled}
                  onToggleAnimation={() => setAnimationEnabled((prev) => !prev)}
                  defaultViewMode={viewMode}
                  onChangeDefaultView={setViewMode}
                />
              </div>
            </div>
          )}
        </main>
      </div>

      {/* 4. Right-Side File Preview Drawer */}
      {selectedFile && (
        <ErrorBoundary fallbackTitle="Preview Error" onReset={() => setSelectedFile(null)}>
          <PreviewDrawer
            file={selectedFile}
            onClose={() => setSelectedFile(null)}
            onOpenFile={handleOpenFile}
          />
        </ErrorBoundary>
      )}
    </div>
  );
};
