import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { FigmaIcon, FigmaIconName } from './components/common/FigmaIcon';
import { CATEGORIES_CONFIG } from './config/categories';
import { apiClient } from './api/client';
import {
  SearchResultItem,
  SystemStatus,
  FolderItem,
  SearchHistoryItem,
  SavedSearchItem,
  IndexingStatus,
  PrivacyStatus,
  StorageAnalytics,
} from './api/types';
import { PreviewDrawer } from './components/preview/PreviewDrawer';
import { FolderManager } from './components/indexing/FolderManager';
import { SearchHistoryView } from './components/history/SearchHistoryView';
import { SavedSearchesView } from './components/history/SavedSearchesView';
import { SettingsDialog } from './components/settings/SettingsDialog';
import { PersonsView } from './components/persons/PersonsView';
import { PasswordModal } from './components/common/PasswordModal';
import { CursorTrailOverlay } from './components/common/CursorTrailOverlay';
import { ErrorBoundary } from './components/common/ErrorBoundary';

type ViewMode = 'files' | 'gallery' | 'analysis' | 'folders' | 'history' | 'persons';

export const App: React.FC = () => {
  // DOM & Animation Refs
  const shellRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const target = useRef({ x: 0.62, y: 0.3 });
  const current = useRef({ x: 0.62, y: 0.3 });
  const raf = useRef(0);

  // App Navigation & UI Views
  const [view, setView] = useState<ViewMode>('files');
  const [compact, setCompact] = useState(false);
  const [selectedFile, setSelectedFile] = useState<SearchResultItem | null>(null);
  const [notice, setNotice] = useState('');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showAddFolderModal, setShowAddFolderModal] = useState(false);
  const [historyTab, setHistoryTab] = useState<'history' | 'saved'>('history');

  // V4 Persons & Privacy State
  const [personsCount, setPersonsCount] = useState(0);
  const [privacyToken, setPrivacyToken] = useState<string | null>(() =>
    sessionStorage.getItem('file_xtractor_privacy_token')
  );
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus>({
    is_configured: false,
    is_unlocked: false,
  });
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordModalMode, setPasswordModalMode] = useState<'verify' | 'setup' | 'recover'>('verify');
  const [pendingProtectedAction, setPendingProtectedAction] = useState<(() => void) | null>(null);

  // Voice Search Recording State
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('ALL');
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [smartMode, setSmartMode] = useState(false);
  const [sortOption, setSortOption] = useState<'relevance' | 'az' | 'za' | 'date' | 'size'>('relevance');
  const [isSearching, setIsSearching] = useState(false);
  const [searchElapsedMs, setSearchElapsedMs] = useState(0);

  // Data States
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [recentFiles, setRecentFiles] = useState<SearchResultItem[]>([]);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearchItem[]>([]);
  const [indexingStatus, setIndexingStatus] = useState<IndexingStatus>({
    is_scanning: false,
    current_folder: '',
    current_file: '',
    current_count: 0,
    total_count: 0,
    failures: 0,
  });

  // Settings
  const [animationEnabled, setAnimationEnabled] = useState(true);
  const [cursorTrailEnabled, setCursorTrailEnabled] = useState(true);

  // Storage Analytics State
  const [storageAnalytics, setStorageAnalytics] = useState<StorageAnalytics | null>(null);
  const [loadingStorage, setLoadingStorage] = useState(false);

  // Recently Opened Files State
  const [recentlyOpened, setRecentlyOpened] = useState<SearchResultItem[]>(() => {
    try {
      const raw = localStorage.getItem('file_xtractor_recently_opened');
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [recentFilterMode, setRecentFilterMode] = useState<'opened' | 'indexed'>('opened');
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);

  // 1. Mouse physics loop for interactive gradient background
  useEffect(() => {
    if (!animationEnabled) return;

    const onPointerMove = (event: PointerEvent) => {
      target.current = {
        x: event.clientX / window.innerWidth,
        y: event.clientY / window.innerHeight,
      };
    };
    window.addEventListener('pointermove', onPointerMove);

    const tick = () => {
      current.current.x += (target.current.x - current.current.x) * 0.045;
      current.current.y += (target.current.y - current.current.y) * 0.045;
      const element = shellRef.current;
      if (element) {
        element.style.setProperty('--mouse-x', `${current.current.x * 100}%`);
        element.style.setProperty('--mouse-y', `${current.current.y * 100}%`);
        element.style.setProperty('--shift-x', `${(1 - current.current.x) * 100}%`);
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      cancelAnimationFrame(raf.current);
    };
  }, [animationEnabled]);

  // 2. Auto-dismiss Toast
  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(''), 2400);
    return () => clearTimeout(timeout);
  }, [notice]);

  // 3. Load Initial System & Backend Data
  const refreshSystemData = useCallback(async () => {
    // Fetch instant metadata immediately (takes ~15ms)
    apiClient.getRecentFiles(40).then((r) => setRecentFiles(r || [])).catch(() => {});
    apiClient.getFolders().then((f) => setFolders(f || [])).catch(() => {});
    apiClient.getSearchHistory(40).then((h) => setHistory(h || [])).catch(() => {});
    apiClient.getSavedSearches().then((s) => setSavedSearches(s || [])).catch(() => {});
    apiClient.listPersons(true, privacyToken).then((p) => setPersonsCount(p.length)).catch(() => {});
    apiClient.getPrivacyStatus(privacyToken).then(setPrivacyStatus).catch(() => {});

    // Fetch heavier AI neural engine status concurrently
    apiClient.getStatus().then((st) => {
      setSystemStatus(st);
      if (st.indexing) setIndexingStatus(st.indexing);
    }).catch((err) => {
      console.warn('Backend status warning:', err);
    });
  }, [privacyToken]);

  useEffect(() => {
    refreshSystemData();
    // Poll indexing status periodically
    const interval = setInterval(async () => {
      try {
        const idx = await apiClient.getIndexingStatus();
        setIndexingStatus(idx);
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshSystemData]);

  // Load storage analytics when in analysis view
  const loadStorageAnalytics = useCallback(async () => {
    setLoadingStorage(true);
    try {
      const data = await apiClient.getStorageAnalytics(privacyToken);
      setStorageAnalytics(data);
    } catch (err) {
      console.error('Failed to load storage analytics:', err);
    } finally {
      setLoadingStorage(false);
    }
  }, [privacyToken]);

  useEffect(() => {
    if (view === 'analysis') {
      loadStorageAnalytics();
    }
  }, [view, loadStorageAnalytics]);

  // Privacy lock and unlock handlers
  const handleLockPrivacy = async () => {
    try {
      await apiClient.lockPrivacy();
    } catch {}
    setPrivacyToken(null);
    sessionStorage.removeItem('file_xtractor_privacy_token');
    setNotice('Privacy locked');
    apiClient.getPrivacyStatus(null).then(setPrivacyStatus).catch(() => {});
    apiClient.getRecentFiles(40).then((r) => setRecentFiles(r || [])).catch(() => {});
    if (hasSearched && searchQuery.trim()) {
      executeSearch(searchQuery, activeCategory, selectedFormats, null);
    }
  };

  const handlePrivacyUnlocked = (token: string) => {
    setPrivacyToken(token);
    sessionStorage.setItem('file_xtractor_privacy_token', token);
    setShowPasswordModal(false);
    setNotice('Protected files unlocked');
    apiClient.getPrivacyStatus(token).then(setPrivacyStatus).catch(() => {});
    apiClient.getRecentFiles(40).then((r) => setRecentFiles(r || [])).catch(() => {});
    apiClient.listPersons(true, token).then((p) => setPersonsCount(p.length)).catch(() => {});
    if (hasSearched && searchQuery.trim()) {
      executeSearch(searchQuery, activeCategory, selectedFormats, token);
    }
    if (pendingProtectedAction) {
      pendingProtectedAction();
      setPendingProtectedAction(null);
    }
  };

  // 4. Keyboard Shortcuts (⌘ N / Ctrl+N for new extraction)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        setShowAddFolderModal(true);
      }
      if (e.key === 'Escape') {
        if (selectedFile) setSelectedFile(null);
        if (showSettingsModal) setShowSettingsModal(false);
        if (showAddFolderModal) setShowAddFolderModal(false);
        if (showPasswordModal) setShowPasswordModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedFile, showSettingsModal, showAddFolderModal, showPasswordModal]);

  // 5. Execute Backend Search
  const executeSearch = useCallback(
    async (
      queryText: string,
      category = activeCategory,
      formats = selectedFormats,
      token = privacyToken
    ) => {
      const trimmed = queryText.trim();
      if (!trimmed) {
        setHasSearched(false);
        setSearchResults([]);
        return;
      }

      setIsSearching(true);
      const startTime = performance.now();
      try {
        const resp = await apiClient.search({
          query: trimmed,
          category: category === 'ALL' ? undefined : category,
          formats: formats.length > 0 ? formats : undefined,
          limit: 60,
          save_history: true,
          privacy_token: token || undefined,
        });

        setSearchResults(resp.results || []);
        setHasSearched(true);
        setSearchElapsedMs(Math.round(performance.now() - startTime));

        // Refresh search history in background
        apiClient.getSearchHistory(30).then(setHistory).catch(() => {});
      } catch (err) {
        console.error('Search failed:', err);
        setNotice('Search error. Verify backend status.');
      } finally {
        setIsSearching(false);
      }
    },
    [activeCategory, selectedFormats, privacyToken]
  );

  // Voice Search Handler via Sarvam Saaras
  const handleToggleVoiceSearch = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
    } else {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          setNotice('Microphone not supported on this device');
          return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunksRef.current = [];
        const mimeType = MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : MediaRecorder.isTypeSupported('audio/ogg')
          ? 'audio/ogg'
          : '';
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.onstop = async () => {
          stream.getTracks().forEach((track) => track.stop());
          const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
          if (audioBlob.size < 100) {
            setNotice('Audio recording too short');
            return;
          }
          setNotice('Transcribing speech with Sarvam Saaras...');
          setIsSearching(true);
          try {
            const result = await apiClient.voiceSearch(audioBlob, privacyToken);
            if (result.transcript && result.transcript.trim()) {
              const query = result.transcript.trim();
              setSearchQuery(query);
              setNotice(`Recognized: "${query}" (${result.language || 'auto'})`);
              if (view !== 'files' && view !== 'gallery') {
                setView('files');
              }
              executeSearch(query);
            } else {
              setNotice('No speech recognized in audio');
            }
          } catch (err: any) {
            console.error('Voice search failed:', err);
            setNotice(err.message || 'Voice search failed');
          } finally {
            setIsSearching(false);
          }
        };

        recorder.start();
        setIsRecording(true);
        setNotice('Listening... Click mic again to finish');
      } catch (err) {
        console.error('Microphone access error:', err);
        setNotice('Microphone access denied or unavailable');
      }
    }
  };

  const handleSearchSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (view !== 'files' && view !== 'gallery') {
      setView('files');
    }
    executeSearch(searchQuery);
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setHasSearched(false);
    setSearchResults([]);
  };

  // 6. Category & Format Filter Handlers
  const handleSelectCategory = (catId: string) => {
    setActiveCategory(catId);
    setSelectedFormats([]);
    if (hasSearched && searchQuery.trim()) {
      executeSearch(searchQuery, catId, []);
    }
  };

  const toggleFormat = (fmt: string) => {
    const nextFormats = selectedFormats.includes(fmt)
      ? selectedFormats.filter((f) => f !== fmt)
      : [...selectedFormats, fmt];
    setSelectedFormats(nextFormats);
    if (hasSearched && searchQuery.trim()) {
      executeSearch(searchQuery, activeCategory, nextFormats);
    }
  };

  // 7. Determine active file list based on view & search
  const visibleFiles = useMemo(() => {
    let list: SearchResultItem[];
    if (hasSearched) {
      list = [...searchResults];
    } else if (recentFilterMode === 'opened' && recentlyOpened.length > 0) {
      list = [...recentlyOpened];
    } else {
      list = [...recentFiles];
    }

    // Filter by Gallery view (images only)
    if (view === 'gallery') {
      list = list.filter((f) => {
        const ext = (f.extension || '').toLowerCase();
        return (
          f.category === 'IMAGE' ||
          ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.svg'].includes(ext)
        );
      });
    }

    // Filter by Category if not in search or not ALL
    if (!hasSearched && activeCategory !== 'ALL') {
      list = list.filter((f) => f.category?.toUpperCase() === activeCategory.toUpperCase());
    }

    // Filter by Formats
    if (selectedFormats.length > 0) {
      list = list.filter((f) => {
        const ext = (f.extension || '').toLowerCase().replace('.', '');
        return selectedFormats.map((sf) => sf.toLowerCase()).includes(ext);
      });
    }

    // Sort files
    list.sort((a, b) => {
      if (sortOption === 'az') return a.filename.localeCompare(b.filename);
      if (sortOption === 'za') return b.filename.localeCompare(a.filename);
      if (sortOption === 'size') return (b.size_bytes || 0) - (a.size_bytes || 0);
      if (sortOption === 'date') {
        const da = new Date(a.modified_at || a.created_at || 0).getTime();
        const db = new Date(b.modified_at || b.created_at || 0).getTime();
        return db - da;
      }
      // default: relevance if searching, else date
      if (hasSearched) return (b.relevance_score || 0) - (a.relevance_score || 0);
      return a.filename.localeCompare(b.filename);
    });

    return list;
  }, [hasSearched, searchResults, recentFiles, recentlyOpened, recentFilterMode, view, activeCategory, selectedFormats, sortOption]);

  // Helpers
  const formatBytes = (bytes?: number) => {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + (sizes[i] || 'B');
  };

  const formatRelativeTime = (val?: string | number) => {
    if (!val) return 'Recently';
    try {
      const d = new Date(val);
      if (isNaN(d.getTime())) return 'Recently';
      const diffMs = Date.now() - d.getTime();
      const diffMin = Math.round(diffMs / 60000);
      if (diffMin < 1) return 'Just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHours = Math.round(diffMin / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      const diffDays = Math.round(diffHours / 24);
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return 'Recently';
    }
  };

  const getFileKind = (file: SearchResultItem): 'image' | 'document' | 'archive' | 'video' | 'audio' | 'code' => {
    const ext = (file.extension || '').toLowerCase();
    const cat = (file.category || '').toUpperCase();
    if (cat === 'IMAGE' || ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.svg'].includes(ext)) {
      return 'image';
    }
    if (cat === 'ARCHIVE' || ['.zip', '.rar', '.7z', '.tar', '.gz'].includes(ext)) {
      return 'archive';
    }
    if (cat === 'VIDEO' || ['.mp4', '.mkv', '.avi', '.mov', '.webm'].includes(ext)) {
      return 'video';
    }
    if (cat === 'AUDIO' || ['.mp3', '.wav', '.flac', '.m4a', '.aac'].includes(ext)) {
      return 'audio';
    }
    if (cat === 'CODE' || ['.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.sql'].includes(ext)) {
      return 'code';
    }
    return 'document';
  };

  const getFileFigmaIcon = (file: SearchResultItem): FigmaIconName => {
    const kind = getFileKind(file);
    if (kind === 'image') return 'image';
    if (kind === 'archive') return 'folder';
    if (kind === 'video') return 'video';
    if (kind === 'audio') return 'music';
    if (kind === 'code') return 'code';
    return 'file';
  };

  const handleOpenFile = (path: string, reveal = false, fileObj?: SearchResultItem) => {
    const targetFile = fileObj || visibleFiles.find((f) => f.path === path) || recentFiles.find((f) => f.path === path);
    if (targetFile) {
      setRecentlyOpened((prev) => {
        const filtered = prev.filter((f) => f.path !== targetFile.path && f.file_id !== targetFile.file_id);
        const updated = [targetFile, ...filtered].slice(0, 30);
        try {
          localStorage.setItem('file_xtractor_recently_opened', JSON.stringify(updated));
        } catch {}
        return updated;
      });
    }

    if (fileObj?.is_locked && !privacyToken) {
      setPendingProtectedAction(() => () => {
        apiClient
          .openFile(path, reveal, sessionStorage.getItem('file_xtractor_privacy_token'))
          .then(() => setNotice(reveal ? 'Revealed in file manager' : 'Opened file'))
          .catch((err: any) => setNotice(err.message || 'Could not open file'));
      });
      setPasswordModalMode(privacyStatus.is_configured ? 'verify' : 'setup');
      setShowPasswordModal(true);
      return;
    }

    apiClient
      .openFile(path, reveal, privacyToken)
      .then(() => setNotice(reveal ? 'Revealed in file manager' : 'Opened file'))
      .catch((err: any) => {
        if (err.message && (err.message.includes('password') || err.message.includes('Protected'))) {
          setPendingProtectedAction(() => () => {
            apiClient
              .openFile(path, reveal, sessionStorage.getItem('file_xtractor_privacy_token'))
              .then(() => setNotice(reveal ? 'Revealed in file manager' : 'Opened file'))
              .catch(() => setNotice('Could not open file'));
          });
          setPasswordModalMode(privacyStatus.is_configured ? 'verify' : 'setup');
          setShowPasswordModal(true);
        } else {
          setNotice('Could not open file directly');
        }
      });
  };

  // Add folder handler
  const handleAddFolder = async (path: string) => {
    try {
      await apiClient.addFolder(path);
      setNotice('Folder added to index library');
      setShowAddFolderModal(false);
      refreshSystemData();
      apiClient.triggerRescan(path).catch(() => {});
    } catch (err) {
      setNotice('Failed to add folder');
    }
  };

  // Total counts
  const totalFilesCount = systemStatus?.total_files || recentFiles.length;
  const imageCount =
    systemStatus?.category_counts?.IMAGE ||
    recentFiles.filter((f) => getFileKind(f) === 'image').length;

  return (
    <ErrorBoundary>
      <main ref={shellRef} className="app-shell select-none">
        {/* Cursor Reactive Gradient Orbs & Noise Texture */}
        <div className="orb orb-primary" />
        <div className="orb orb-secondary" />
        <div className="pointer-aura" />
        <div className="noise" />

        {/* 1. Left Floating Glass Sidebar */}
        <aside className="app-sidebar">
          {/* Brand Header */}
          <div className="app-brand">
            <span className="brand-icon">
              <FigmaIcon name="logo" size={20} />
            </span>
            <span className="font-brigold text-xl tracking-wide font-normal" style={{ fontFamily: "'Brigold', 'Brigold DEMO', sans-serif" }}>
              i file
            </span>
          </div>

          {/* Quick Action Button */}
          <button
            className="new-file"
            type="button"
            onClick={() => setShowAddFolderModal(true)}
            title="Add folder to index (Ctrl+N)"
          >
            <FigmaIcon name="plus" size={17} />
            <span>New extraction</span>
            <kbd>⌘ N</kbd>
          </button>

          {/* Primary Navigation */}
          <nav className="primary-nav" aria-label="Workspace navigation">
            <button
              className={view === 'files' ? 'active' : ''}
              type="button"
              onClick={() => {
                setView('files');
                handleClearSearch();
              }}
            >
              <FigmaIcon name="folder" size={17} />
              <span>My Files</span>
              <small>{totalFilesCount}</small>
            </button>

            <button
              className={view === 'gallery' ? 'active' : ''}
              type="button"
              onClick={() => {
                setView('gallery');
                handleClearSearch();
              }}
            >
              <FigmaIcon name="gallery" size={17} />
              <span>Gallery</span>
              <small>{imageCount}</small>
            </button>

            <button
              className={view === 'persons' ? 'active' : ''}
              type="button"
              onClick={() => setView('persons')}
            >
              <FigmaIcon name="person" size={17} />
              <span>Persons</span>
              <small>{personsCount}</small>
            </button>

            <button
              className={view === 'analysis' ? 'active' : ''}
              type="button"
              onClick={() => setView('analysis')}
            >
              <FigmaIcon name="analysis" size={17} />
              <span>Analysis</span>
            </button>

            <button
              className={view === 'folders' ? 'active' : ''}
              type="button"
              onClick={() => setView('folders')}
            >
              <FigmaIcon name="archive" size={17} />
              <span>Folders</span>
              <small>{folders.length}</small>
            </button>

            <button
              className={view === 'history' ? 'active' : ''}
              type="button"
              onClick={() => setView('history')}
            >
              <FigmaIcon name="clock" size={17} />
              <span>History</span>
              <small>{history.length}</small>
            </button>
          </nav>

          {/* Recently Added Files Section */}
          <div className="recent-files">
            <div className="sidebar-heading">
              <span>Recently added</span>
              <button
                type="button"
                aria-label="Refresh"
                onClick={refreshSystemData}
                title="Refresh recently added"
              >
                <FigmaIcon name="more" size={15} />
              </button>
            </div>

            {recentFiles.slice(0, 4).map((file) => (
              <button
                type="button"
                key={file.file_id}
                onClick={() => {
                  setSelectedFile(file);
                }}
                title={file.filename}
              >
                <span>
                  <FigmaIcon name={getFileFigmaIcon(file)} size={15} />
                </span>
                <span>{file.filename}</span>
              </button>
            ))}
          </div>

          {/* Sidebar Footer: Privacy Status, Settings & Indexing Bar */}
          <div className="sidebar-footer">
            {privacyStatus.is_configured && (
              <button
                type="button"
                onClick={() => {
                  if (privacyToken) {
                    handleLockPrivacy();
                  } else {
                    setPasswordModalMode('verify');
                    setShowPasswordModal(true);
                  }
                }}
                className={`sidebar-privacy-btn w-full flex items-center justify-between px-3 py-2 rounded-xl mb-1 text-xs transition-colors ${
                  privacyToken
                    ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20 hover:bg-amber-500/20'
                    : 'bg-white/[0.04] text-zinc-400 border border-white/[0.08] hover:text-white'
                }`}
                title={privacyToken ? 'Click to lock privacy mode' : 'Click to unlock protected files'}
              >
                <span className="flex items-center gap-2">
                  <FigmaIcon name={privacyToken ? 'unlock' : 'lock'} size={15} />
                  <span>{privacyToken ? 'Privacy Unlocked' : 'Privacy Locked'}</span>
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-black/30">
                  {privacyToken ? 'Lock' : 'Unlock'}
                </span>
              </button>
            )}

            <button type="button" className="sidebar-settings-btn" onClick={() => setShowSettingsModal(true)}>
              <FigmaIcon name="settings" size={17} />
              <span>Settings</span>
              <FigmaIcon name="chevron" size={13} />
            </button>

            <div className="storage-copy">
              <span>
                {indexingStatus.is_scanning
                  ? 'Scanning files...'
                  : `${totalFilesCount} files indexed`}
              </span>
              <span>100%</span>
            </div>
            <div className="storage-bar">
              <i style={{ width: indexingStatus.is_scanning ? '80%' : '100%' }} />
            </div>
          </div>
        </aside>

        {/* 2. Main Workspace */}
        <section className="workspace">
          {/* Hero Greeting & Search Header (Visible on Files & Gallery views) */}
          {(view === 'files' || view === 'gallery') && (
            <>
              {/* Rotating Starburst Greeting */}
              <div className="hero-greeting">
                <span className="greeting-mark" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
                <h1 className="font-brigold" style={{ fontFamily: "'Brigold', 'Brigold DEMO', sans-serif" }}>
                  Hey There
                </h1>
              </div>

              {/* Centered Hero Search Bar */}
              <div className="hero-search relative" role="search">
                <form onSubmit={handleSearchSubmit} className="search-field">
                  <FigmaIcon name="search" size={20} />
                  <input
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      if (!e.target.value) handleClearSearch();
                    }}
                    onFocus={() => setShowSearchDropdown(true)}
                    onBlur={() => setTimeout(() => setShowSearchDropdown(false), 250)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setShowSearchDropdown(false);
                        handleSearchSubmit();
                      }
                      if (e.key === 'Escape') {
                        setShowSearchDropdown(false);
                      }
                    }}
                    placeholder="Search files, text, people, dates, or metadata..."
                    autoFocus
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={handleClearSearch}
                      className="text-zinc-500 hover:text-white text-xs px-2"
                      title="Clear"
                    >
                      ✕
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleToggleVoiceSearch}
                    className={`p-1.5 rounded-lg transition-all ${
                      isRecording
                        ? 'bg-rose-500 text-white animate-pulse'
                        : 'text-zinc-400 hover:text-white hover:bg-white/10'
                    }`}
                    title={isRecording ? 'Listening... click to finish' : 'Voice Search (Sarvam Saaras)'}
                  >
                    <FigmaIcon name="mic" size={17} />
                  </button>
                </form>

                {/* Floating Recent Searches Dropdown */}
                {showSearchDropdown && history.filter((h) => (h.query || (h as any).query_text)?.trim()).length > 0 && !searchQuery && (
                  <div className="absolute top-[52px] left-0 right-0 p-2 bg-zinc-900/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-2xl z-50 animate-fadeIn">
                    <div className="flex items-center justify-between px-3 py-1.5 text-[10px] text-zinc-400 font-semibold uppercase tracking-wider border-b border-white/[0.06] mb-1">
                      <span className="flex items-center gap-1.5">
                        <FigmaIcon name="clock" size={12} />
                        <span>Recent Searches</span>
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onMouseDown={async (e) => {
                            e.preventDefault();
                            await apiClient.clearSearchHistory();
                            setHistory([]);
                            setShowSearchDropdown(false);
                          }}
                          className="text-[10px] text-zinc-500 hover:text-rose-400 font-normal transition-colors"
                        >
                          Clear
                        </button>
                        <button
                          type="button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            setShowSearchDropdown(false);
                          }}
                          className="text-zinc-500 hover:text-white"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    <div className="space-y-0.5 max-h-52 overflow-y-auto">
                      {history
                        .filter((item) => (item.query || (item as any).query_text)?.trim())
                        .slice(0, 6)
                        .map((item, idx) => {
                          const qText = (item.query || (item as any).query_text || '').trim();
                          return (
                            <div
                              key={idx}
                              onMouseDown={(e) => {
                                e.preventDefault();
                                if (!qText) return;
                                setSearchQuery(qText);
                                setShowSearchDropdown(false);
                                executeSearch(qText);
                              }}
                              className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-zinc-300 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                            >
                              <div className="flex items-center gap-2 truncate">
                                <FigmaIcon name="search" size={13} />
                                <span className="truncate">{qText}</span>
                              </div>
                              <span className="text-[10px] text-zinc-500 font-mono">
                                {item.result_count ?? 0} results
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}

                <div className="search-controls">
                  <div>
                    <button
                      className="search-add"
                      type="button"
                      onClick={() => setShowAddFolderModal(true)}
                      aria-label="Add folder"
                      title="Add folder to library"
                    >
                      <FigmaIcon name="plus" size={17} />
                    </button>
                    <button
                      className={`mode-chip ${!smartMode ? 'active' : ''}`}
                      type="button"
                      onClick={() => {
                        setSmartMode(false);
                        setNotice('Standard Hybrid BM25 + SBERT search active');
                      }}
                    >
                      Search
                    </button>
                    <button
                      className={`mode-chip ${smartMode ? 'active' : ''}`}
                      type="button"
                      onClick={() => {
                        setSmartMode(true);
                        setNotice('Smart Compositional AI + Vision search active');
                      }}
                    >
                      <FigmaIcon name="sparkles" size={13} />
                      Smart
                    </button>
                  </div>

                  <div>
                    <span>
                      {view === 'gallery'
                        ? 'Images only'
                        : activeCategory === 'ALL'
                        ? 'All files'
                        : activeCategory}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSortOption((prev) => (prev === 'az' ? 'za' : 'az'));
                        setNotice(`Sorting ${sortOption === 'az' ? 'Z–A' : 'A–Z'}`);
                      }}
                      aria-label="Toggle sort order"
                      title="Toggle sort order"
                    >
                      <FigmaIcon name="sort" size={17} />
                    </button>
                  </div>
                </div>

                {/* Glowing laser hairline indicator following cursor */}
                <i />
              </div>

              {/* Horizontal Category Chips Bar */}
              <div className="category-bar">
                {CATEGORIES_CONFIG.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    className={`category-chip ${activeCategory === cat.id ? 'active' : ''}`}
                    onClick={() => handleSelectCategory(cat.id)}
                  >
                    <span>{cat.label}</span>
                  </button>
                ))}
              </div>

              {/* Expandable Format Pills if selected category has specific formats */}
              {CATEGORIES_CONFIG.find((c) => c.id === activeCategory)?.formats && (
                <div className="flex items-center gap-1.5 overflow-x-auto py-1 mb-3 scrollbar-none">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider mr-1">
                    Formats:
                  </span>
                  {CATEGORIES_CONFIG.find((c) => c.id === activeCategory)?.formats?.map((fmt) => {
                    const isSelected = selectedFormats.includes(fmt.ext);
                    return (
                      <button
                        key={fmt.ext}
                        type="button"
                        onClick={() => toggleFormat(fmt.ext)}
                        className={`text-[9.5px] px-2.5 py-1 rounded-full border transition-all ${
                          isSelected
                            ? 'bg-white text-zinc-950 border-white font-bold shadow-sm'
                            : 'bg-white/[0.04] text-zinc-400 border-white/[0.08] hover:text-white hover:border-white/20'
                        }`}
                        style={isSelected ? { backgroundColor: '#ffffff', color: '#09090b' } : {}}
                      >
                        {fmt.label}
                      </button>
                    );
                  })}
                  {selectedFormats.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedFormats([])}
                      className="text-[9.5px] text-zinc-500 hover:text-rose-400 ml-2"
                    >
                      Clear formats
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          {/* 3. Panel Views */}
          {/* Analysis View */}
          {/* Analysis View -> Storage Analytics Dashboard */}
          {view === 'analysis' && (
            <section className="analytics-panel space-y-6">
              <div className="analytics-head">
                <div>
                  <span className="eyebrow">Capacity & Storage Intelligence</span>
                  <h2>Storage Analytics & Library Capacity</h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={loadStorageAnalytics}
                    className="px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-zinc-300 text-xs font-medium border border-white/[0.08] transition-colors"
                  >
                    Refresh
                  </button>
                  <strong className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-xl text-xs">
                    {storageAnalytics ? formatBytes(storageAnalytics.total_bytes) : 'Calculating...'}
                  </strong>
                </div>
              </div>

              {loadingStorage && !storageAnalytics ? (
                <div className="py-20 text-center text-zinc-500 text-sm">
                  Calculating disk and storage metrics across indexed libraries...
                </div>
              ) : storageAnalytics ? (
                <div className="space-y-6">
                  {/* Top 4 Metrics Cards */}
                  <div className="metrics">
                    <div>
                      <span>Total space used</span>
                      <strong>{formatBytes(storageAnalytics.total_bytes)}</strong>
                      <small>{storageAnalytics.total_files.toLocaleString()} files indexed</small>
                    </div>
                    <div>
                      <span>Protected files</span>
                      <strong className="text-amber-400">{storageAnalytics.protected_files} Files</strong>
                      <small>{formatBytes(storageAnalytics.protected_bytes)} privacy locked</small>
                    </div>
                    <div>
                      <span>Monitored libraries</span>
                      <strong>{storageAnalytics.folders.length} Folders</strong>
                      <small>Background watcher active</small>
                    </div>
                    <div>
                      <span>Duplicate waste</span>
                      <strong className="text-emerald-400">{formatBytes(storageAnalytics.duplicate_bytes)}</strong>
                      <small>{storageAnalytics.duplicate_files} duplicate files</small>
                    </div>
                  </div>

                  {/* Storage by Category Multi-Segment Progress Bar */}
                  <div className="p-5 rounded-2xl bg-zinc-900/60 border border-white/[0.08] space-y-4">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                        Storage by Category Breakdown
                      </span>
                      <span className="text-zinc-400">
                        {storageAnalytics.categories.length} active categories
                      </span>
                    </div>

                    {/* Proportional Segment Bar */}
                    <div className="h-3 w-full rounded-full bg-white/[0.05] overflow-hidden flex">
                      {storageAnalytics.categories.map((cat) => {
                        const pct = storageAnalytics.total_bytes > 0
                          ? (cat.bytes / storageAnalytics.total_bytes) * 100
                          : 0;
                        if (pct < 0.2) return null;
                        return (
                          <div
                            key={cat.name}
                            style={{ width: `${pct}%`, backgroundColor: cat.color }}
                            className="h-full transition-all duration-300"
                            title={`${cat.name}: ${formatBytes(cat.bytes)} (${pct.toFixed(1)}%)`}
                          />
                        );
                      })}
                    </div>

                    {/* Category Cards Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2.5 pt-2">
                      {storageAnalytics.categories.map((cat) => {
                        const pct = storageAnalytics.total_bytes > 0
                          ? ((cat.bytes / storageAnalytics.total_bytes) * 100).toFixed(1)
                          : '0';
                        return (
                          <div
                            key={cat.name}
                            className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] space-y-1 hover:bg-white/[0.05] transition-colors"
                          >
                            <div className="flex items-center gap-1.5">
                              <span
                                className="w-2.5 h-2.5 rounded-full shrink-0"
                                style={{ backgroundColor: cat.color }}
                              />
                              <span className="text-xs font-semibold text-zinc-200 truncate">{cat.name}</span>
                            </div>
                            <div className="text-sm font-bold text-white">{formatBytes(cat.bytes)}</div>
                            <div className="text-[10px] text-zinc-500">
                              {cat.count} files · {pct}%
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Monitored Folders Capacity Breakdown */}
                  <div className="p-5 rounded-2xl bg-zinc-900/60 border border-white/[0.08] space-y-3">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                        Indexed Library Distribution
                      </span>
                      <button
                        type="button"
                        onClick={() => setView('folders')}
                        className="text-xs text-sky-400 hover:underline"
                      >
                        Manage Folders →
                      </button>
                    </div>

                    <div className="divide-y divide-white/[0.04]">
                      {storageAnalytics.folders.map((fo) => {
                        const pct = storageAnalytics.total_bytes > 0
                          ? ((fo.bytes / storageAnalytics.total_bytes) * 100).toFixed(1)
                          : '0';
                        return (
                          <div key={fo.path} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                            <div className="min-w-0 flex-1">
                              <div className="font-medium text-white truncate">{fo.name}</div>
                              <div className="text-[10px] text-zinc-500 truncate font-mono">{fo.path}</div>
                            </div>
                            <div className="text-right shrink-0">
                              <div className="font-bold text-white">{formatBytes(fo.bytes)}</div>
                              <div className="text-[10px] text-zinc-400">
                                {fo.count} files · {pct}% of storage
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Top 15 Largest Files on Disk */}
                  <div className="p-5 rounded-2xl bg-zinc-900/60 border border-white/[0.08] space-y-3">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                        Top Largest Files on Disk
                      </span>
                      <span className="text-[10px] text-zinc-500">Fast space optimization</span>
                    </div>

                    <div className="divide-y divide-white/[0.04]">
                      {storageAnalytics.largest_files.map((file, idx) => (
                        <div
                          key={file.id}
                          className="py-2.5 flex items-center justify-between gap-3 text-xs hover:bg-white/[0.02] px-2 rounded-lg transition-colors"
                        >
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <span className="text-[11px] font-mono text-zinc-600 w-5 text-right">{idx + 1}</span>
                            <FigmaIcon name="file" size={16} />
                            <div className="min-w-0 flex-1 truncate">
                              <div className="font-medium text-white truncate flex items-center gap-2">
                                <span className="truncate">{file.filename}</span>
                                {file.is_protected && (
                                  <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                    Protected
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-zinc-500 truncate font-mono">{file.path}</div>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 shrink-0">
                            <span className="font-bold font-mono text-white text-xs">
                              {formatBytes(file.size_bytes)}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => handleOpenFile(file.path, false)}
                                className="px-2.5 py-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-zinc-300 hover:text-white text-[11px] font-medium transition-colors"
                                title="Open file"
                              >
                                Open
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenFile(file.path, true)}
                                className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white text-[11px] transition-colors"
                                title="Reveal in File Explorer"
                              >
                                Reveal
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Quick Indexing Actions */}
                  <div className="mt-6 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (folders[0]) {
                          apiClient.triggerRescan(folders[0].path);
                          setNotice('Rescanning index...');
                        } else {
                          setShowAddFolderModal(true);
                        }
                      }}
                      className="btn-white px-4 py-2 rounded-xl font-bold text-xs hover:bg-zinc-200 transition-colors shadow-sm"
                      style={{ backgroundColor: '#ffffff', color: '#09090b' }}
                    >
                      Scan Library Now
                    </button>
                    <button
                      type="button"
                      onClick={() => setView('folders')}
                      className="px-4 py-2 rounded-xl bg-white/[0.06] text-white font-medium text-xs hover:bg-white/[0.1] border border-white/[0.08] transition-colors"
                    >
                      Manage Folders
                    </button>
                  </div>
                </div>
              ) : null}
            </section>
          )}

          {/* Folders Management View */}
          {view === 'folders' && (
            <section className="library-panel">
              <FolderManager
                folders={folders}
                indexingStatus={indexingStatus}
                onAddFolder={handleAddFolder}
                onRemoveFolder={async (p) => {
                  await apiClient.removeFolder(p);
                  setNotice('Folder removed');
                  refreshSystemData();
                }}
                onRescanFolder={async (p) => {
                  await apiClient.triggerRescan(p);
                  setNotice('Folder scan triggered');
                }}
              />
            </section>
          )}

          {/* Persons Management View */}
          {view === 'persons' && (
            <section className="library-panel">
              <PersonsView
                privacyToken={privacyToken}
                onSearchPerson={(personName) => {
                  setSearchQuery(personName);
                  setView('files');
                  executeSearch(personName);
                }}
                onOpenFile={(p) => handleOpenFile(p, false)}
              />
            </section>
          )}

          {/* History & Saved Searches View */}
          {view === 'history' && (
            <section className="library-panel">
              <div className="flex items-center gap-2 mb-4 border-b border-white/[0.08] pb-3">
                <button
                  type="button"
                  onClick={() => setHistoryTab('history')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                    historyTab === 'history'
                      ? 'tab-active-white shadow-sm'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                  style={historyTab === 'history' ? { backgroundColor: '#ffffff', color: '#09090b' } : {}}
                >
                  Search History ({history.length})
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryTab('saved')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                    historyTab === 'saved'
                      ? 'tab-active-white shadow-sm'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                  style={historyTab === 'saved' ? { backgroundColor: '#ffffff', color: '#09090b' } : {}}
                >
                  Saved Searches ({savedSearches.length})
                </button>
              </div>

              {historyTab === 'history' ? (
                <SearchHistoryView
                  history={history}
                  onSelectQuery={(q) => {
                    setSearchQuery(q);
                    setView('files');
                    executeSearch(q);
                  }}
                  onClearHistory={async () => {
                    await apiClient.clearSearchHistory();
                    setHistory([]);
                    setNotice('Search history cleared');
                  }}
                />
              ) : (
                <SavedSearchesView
                  savedSearches={savedSearches}
                  onSelectQuery={(q) => {
                    setSearchQuery(q);
                    setView('files');
                    executeSearch(q);
                  }}
                  onDeleteSavedSearch={async (id) => {
                    await apiClient.deleteSavedSearch(id);
                    setSavedSearches((prev) => prev.filter((s) => s.id !== id));
                    setNotice('Saved search deleted');
                  }}
                />
              )}
            </section>
          )}

          {/* Files / Gallery Library Grid Panel */}
          {(view === 'files' || view === 'gallery') && (
            <section className="library-panel">
              {/* Library Toolbar */}
              <div className="library-toolbar">
                <div className="result-count">
                  <strong>
                    {hasSearched
                      ? `Search results for "${searchQuery}"`
                      : view === 'gallery'
                      ? 'Image library'
                      : 'Recent files'}
                  </strong>
                  <span>
                    {visibleFiles.length} items
                    {hasSearched && searchElapsedMs > 0 ? ` · ${searchElapsedMs}ms` : ''}
                  </span>
                </div>

                <div className="filter-pills">
                  <button
                    className={recentFilterMode === 'opened' && !hasSearched ? 'active' : ''}
                    type="button"
                    onClick={() => {
                      setRecentFilterMode('opened');
                      if (hasSearched) handleClearSearch();
                      setNotice(recentlyOpened.length > 0 ? `Showing ${recentlyOpened.length} recently opened files` : 'No opened files yet in session. Open any file to add it here.');
                    }}
                  >
                    Recently opened {recentlyOpened.length > 0 ? `(${recentlyOpened.length})` : ''}
                  </button>
                  <button
                    className={recentFilterMode === 'indexed' && !hasSearched ? 'active' : ''}
                    type="button"
                    onClick={() => {
                      setRecentFilterMode('indexed');
                      setSortOption('date');
                      if (hasSearched) handleClearSearch();
                      setNotice('Files sorted by latest indexed date');
                    }}
                  >
                    Recently indexed
                  </button>
                  <button type="button" onClick={() => setView('history')}>
                    Search history
                  </button>
                </div>

                <div className="view-actions">
                  <button
                    type="button"
                    onClick={() => {
                      const next =
                        sortOption === 'relevance'
                          ? 'az'
                          : sortOption === 'az'
                          ? 'za'
                          : sortOption === 'za'
                          ? 'date'
                          : sortOption === 'date'
                          ? 'size'
                          : 'relevance';
                      setSortOption(next);
                      setNotice(`Sorting: ${next.toUpperCase()}`);
                    }}
                    title="Change sort"
                  >
                    <FigmaIcon name="sort" size={16} />
                    <span>
                      {sortOption === 'az'
                        ? 'A–Z'
                        : sortOption === 'za'
                        ? 'Z–A'
                        : sortOption === 'date'
                        ? 'Date'
                        : sortOption === 'size'
                        ? 'Size'
                        : 'Relevance'}
                    </span>
                  </button>

                  <button
                    className={compact ? 'active' : ''}
                    type="button"
                    onClick={() => setCompact((v) => !v)}
                    aria-label="Toggle grid or list view"
                    title={compact ? 'Switch to Grid View' : 'Switch to Compact View'}
                  >
                    <FigmaIcon name={compact ? 'grid' : 'filter'} size={17} />
                  </button>
                </div>
              </div>

              {/* Loading State */}
              {isSearching ? (
                <div className="py-20 flex flex-col items-center justify-center text-zinc-400 gap-3">
                  <span className="greeting-mark" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className="text-xs font-medium">Neural retrieval in progress...</span>
                </div>
              ) : visibleFiles.length > 0 ? (
                <div className={`file-grid ${compact ? 'compact' : ''}`}>
                  {visibleFiles.map((file, index) => {
                    const kind = getFileKind(file);
                    const artIndex = (file.file_id % 3) * 2 + 2; // maps to art-2, art-4, art-6
                    const isSelected = selectedFile?.file_id === file.file_id;

                    return (
                      <button
                        key={file.file_id || `${file.path}-${index}`}
                        className={`file-card ${isSelected ? 'selected' : ''}`}
                        type="button"
                        onClick={() => setSelectedFile(file)}
                        style={{ animationDelay: `${Math.min(index * 30, 300)}ms` }}
                      >
                        {/* Preview Section */}
                        <span className={`file-preview art-${artIndex}`}>
                          {file.is_locked && (
                            <span className="lock-badge" title="Protected file">
                              <FigmaIcon name="lock" size={12} />
                            </span>
                          )}
                          {kind === 'image' ? (
                            <img
                              src={apiClient.getThumbnailUrl(file.file_id, 320)}
                              alt={file.filename}
                              loading="lazy"
                              style={file.blur_preview || file.is_locked ? { filter: 'blur(16px)' } : undefined}
                              onError={(e) => {
                                // Graceful fallback to Figma geometric mountain line-art
                                (e.currentTarget as HTMLElement).style.display = 'none';
                                const parent = e.currentTarget.parentElement;
                                if (parent && !parent.querySelector('.mountain-art')) {
                                  const art = document.createElement('span');
                                  art.className = 'mountain-art';
                                  art.innerHTML = '<i/><i/><i/>';
                                  parent.appendChild(art);
                                }
                              }}
                            />
                          ) : kind === 'document' ? (
                            <span className="document-preview">
                              <FigmaIcon name="file" size={42} />
                              <i />
                              <i />
                              <i />
                            </span>
                          ) : kind === 'archive' ? (
                            <span className="archive-preview">
                              <FigmaIcon name="folder" size={44} />
                              <b>ZIP</b>
                            </span>
                          ) : (
                            <span className="document-preview">
                              <FigmaIcon name={getFileFigmaIcon(file)} size={42} />
                            </span>
                          )}

                          {/* Hover Menu Button */}
                          <span
                            className="file-menu"
                            title="Actions"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenFile(file.path, false, file);
                            }}
                          >
                            <FigmaIcon name="external" size={14} />
                          </span>
                        </span>

                        {/* File Info Card Bottom */}
                        <span className="file-info">
                          <span>
                            <strong>{file.filename}</strong>
                            <small>{formatRelativeTime(file.modified_at || file.created_at)}</small>
                          </span>
                          <span className="flex items-center justify-between text-[8.5px] text-zinc-500">
                            <small>
                              {(file.extension || 'FILE').toUpperCase().replace('.', '')} ·{' '}
                              {formatBytes(file.size_bytes)}
                            </small>
                            {file.relevance_score > 0 && (
                              <span className="text-sky-400 font-mono">
                                {Math.round(file.relevance_score * 100)}%
                              </span>
                            )}
                          </span>
                        </span>
                      </button>
                    );
                  })}

                  {/* Drop Card at end of grid */}
                  <button
                    className="drop-card"
                    type="button"
                    onClick={() => setShowAddFolderModal(true)}
                    title="Add local folder to library"
                  >
                    <span>
                      <FigmaIcon name="upload" size={20} />
                    </span>
                    <strong>Add files & folders</strong>
                    <small>Browse your computer</small>
                  </button>
                </div>
              ) : (
                /* Empty State Matching Figma */
                <div className="empty-state">
                  <span>
                    <FigmaIcon name="search" size={24} />
                  </span>
                  <strong>No files found</strong>
                  <p>Try a different search query or add a new folder to index.</p>
                  <button
                    type="button"
                    onClick={() => {
                      handleClearSearch();
                      setActiveCategory('ALL');
                    }}
                  >
                    Clear search
                  </button>
                </div>
              )}
            </section>
          )}
        </section>

        {/* 4. Slide-in Preview Drawer */}
        {selectedFile && (
          <PreviewDrawer
            file={selectedFile}
            onClose={() => setSelectedFile(null)}
            onOpenFile={(path, reveal) => handleOpenFile(path, reveal, selectedFile)}
            onUnlockRequest={() => {
              setPasswordModalMode(privacyStatus.is_configured ? 'verify' : 'setup');
              setShowPasswordModal(true);
            }}
          />
        )}

        {/* 5. Settings Modal Dialog */}
        {showSettingsModal && (
          <div className="modal-backdrop" onClick={() => setShowSettingsModal(false)}>
            <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.08]">
                <h3 className="font-semibold text-white text-base">Application Settings</h3>
                <button
                  type="button"
                  onClick={() => setShowSettingsModal(false)}
                  className="p-1 rounded-lg text-zinc-400 hover:text-white"
                >
                  <FigmaIcon name="close" size={18} />
                </button>
              </div>

              <SettingsDialog
                systemStatus={systemStatus}
                animationEnabled={animationEnabled}
                onToggleAnimation={() => setAnimationEnabled((v) => !v)}
                cursorTrailEnabled={cursorTrailEnabled}
                onToggleCursorTrail={() => setCursorTrailEnabled((v) => !v)}
                defaultViewMode={compact ? 'list' : 'grid'}
                onChangeDefaultView={(m) => setCompact(m === 'list')}
                privacyToken={privacyToken}
                onPrivacyUnlocked={handlePrivacyUnlocked}
              />
            </div>
          </div>
        )}

        {/* 5.5. Password / Privacy Modal */}
        <PasswordModal
          isOpen={showPasswordModal}
          mode={passwordModalMode}
          onClose={() => {
            setShowPasswordModal(false);
            setPendingProtectedAction(null);
          }}
          onSuccess={handlePrivacyUnlocked}
        />

        {/* 6. Add Folder Modal Dialog */}
        {showAddFolderModal && (
          <div className="modal-backdrop" onClick={() => setShowAddFolderModal(false)}>
            <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.08]">
                <h3 className="font-semibold text-white text-base">Index a Local Directory</h3>
                <button
                  type="button"
                  onClick={() => setShowAddFolderModal(false)}
                  className="p-1 rounded-lg text-zinc-400 hover:text-white"
                >
                  <FigmaIcon name="close" size={18} />
                </button>
              </div>

              <p className="text-xs text-zinc-400 mb-4">
                Enter an absolute path to a folder on your computer to scan and index for instant
                neural retrieval, OCR, and AI document understanding.
              </p>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const input = (e.currentTarget.elements.namedItem('folderPath') as HTMLInputElement)
                    ?.value;
                  if (input && input.trim()) {
                    handleAddFolder(input.trim());
                  }
                }}
                className="space-y-4"
              >
                <input
                  name="folderPath"
                  type="text"
                  placeholder="e.g. C:\Users\space\Documents or D:\Projects"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-white/30"
                  autoFocus
                />
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddFolderModal(false)}
                    className="px-4 py-2 rounded-xl text-xs text-zinc-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-white px-4 py-2 rounded-xl font-bold text-xs hover:bg-zinc-200 transition-colors shadow-sm"
                    style={{ backgroundColor: '#ffffff', color: '#09090b' }}
                  >
                    Add and Index
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* 7. Hidden File Input for quick extractions */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="visually-hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              setNotice(`${e.target.files.length} files selected`);
            }
          }}
        />

        {/* 8. Floating Cursor File-Tag Trail Effect */}
        <CursorTrailOverlay enabled={cursorTrailEnabled} />

        {/* 9. Figma Styled Toast Notification */}
        {notice && (
          <div className="toast">
            <span>✓</span>
            {notice}
          </div>
        )}
      </main>
    </ErrorBoundary>
  );
};

export default App;
