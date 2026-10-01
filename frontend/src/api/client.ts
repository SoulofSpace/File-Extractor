import {
  SearchRequest,
  SearchResponse,
  SearchResultItem,
  SystemStatus,
  FolderItem,
  IndexingStatus,
  SearchHistoryItem,
  SavedSearchItem,
  DocumentUnderstanding
} from './types';

const API_BASE = 'http://127.0.0.1:8765';

export const apiClient = {
  async getStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error(`Status failed: ${res.statusText}`);
    return res.json();
  },

  async search(req: SearchRequest): Promise<SearchResponse> {
    const res = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
    return res.json();
  },

  async getRecentFiles(limit = 12, category?: string): Promise<SearchResultItem[]> {
    const url = category
      ? `${API_BASE}/api/recent-files?limit=${limit}&category=${encodeURIComponent(category)}`
      : `${API_BASE}/api/recent-files?limit=${limit}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Get recent files failed: ${res.statusText}`);
    const data = await res.json();
    return data.files || [];
  },

  async getFileDetail(fileId: number): Promise<SearchResultItem & { document_understanding?: DocumentUnderstanding }> {
    const res = await fetch(`${API_BASE}/api/file/${fileId}`);
    if (!res.ok) throw new Error(`Get file detail failed: ${res.statusText}`);
    return res.json();
  },

  getThumbnailUrl(fileId: number, size = 360): string {
    return `${API_BASE}/api/thumbnail/${fileId}?size=${size}`;
  },

  async getFolders(): Promise<FolderItem[]> {
    const res = await fetch(`${API_BASE}/api/folders`);
    if (!res.ok) throw new Error(`Get folders failed: ${res.statusText}`);
    const data = await res.json();
    return data.folders || [];
  },

  async addFolder(path: string): Promise<{ status: string; folder_id: number; path: string }> {
    const res = await fetch(`${API_BASE}/api/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) throw new Error(`Add folder failed: ${res.statusText}`);
    return res.json();
  },

  async removeFolder(path: string): Promise<{ status: string; path: string }> {
    const res = await fetch(`${API_BASE}/api/folders`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) throw new Error(`Remove folder failed: ${res.statusText}`);
    return res.json();
  },

  async triggerRescan(path: string): Promise<{ status: string; path: string }> {
    const res = await fetch(`${API_BASE}/api/indexing/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) throw new Error(`Trigger rescan failed: ${res.statusText}`);
    return res.json();
  },

  async getIndexingStatus(): Promise<IndexingStatus> {
    const res = await fetch(`${API_BASE}/api/indexing/status`);
    if (!res.ok) throw new Error(`Get indexing status failed: ${res.statusText}`);
    return res.json();
  },

  async getSearchHistory(limit = 30): Promise<SearchHistoryItem[]> {
    const res = await fetch(`${API_BASE}/api/history?limit=${limit}`);
    if (!res.ok) throw new Error(`Get history failed: ${res.statusText}`);
    const data = await res.json();
    return data.history || [];
  },

  async clearSearchHistory(): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/history/clear`, { method: 'POST' });
    if (!res.ok) throw new Error(`Clear history failed: ${res.statusText}`);
    return res.json();
  },

  async getSavedSearches(): Promise<SavedSearchItem[]> {
    const res = await fetch(`${API_BASE}/api/saved-searches`);
    if (!res.ok) throw new Error(`Get saved searches failed: ${res.statusText}`);
    const data = await res.json();
    return data.saved_searches || [];
  },

  async addSavedSearch(query: string, name?: string): Promise<SavedSearchItem> {
    const res = await fetch(`${API_BASE}/api/saved-searches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, name }),
    });
    if (!res.ok) throw new Error(`Add saved search failed: ${res.statusText}`);
    return res.json();
  },

  async deleteSavedSearch(id: number): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/saved-searches/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Delete saved search failed: ${res.statusText}`);
    return res.json();
  },

  async openFile(path: string, reveal = false): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/open-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, reveal }),
    });
    if (!res.ok) throw new Error(`Open file failed: ${res.statusText}`);
    return res.json();
  }
};
