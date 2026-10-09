import {
  SearchRequest,
  SearchResponse,
  SearchResultItem,
  SystemStatus,
  FolderItem,
  IndexingStatus,
  SearchHistoryItem,
  SavedSearchItem,
  DocumentUnderstanding,
  Person,
  PersonDetails,
  PrivacyStatus,
  PrivacySettings,
  StorageAnalytics,
  FaceReviewItem,
  FileFaceDetection,
} from './types';

const API_BASE = typeof window !== 'undefined' && window.location?.origin && window.location.origin.startsWith('http')
  ? window.location.origin
  : 'http://127.0.0.1:8765';

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

  async openFile(path: string, reveal = false, privacyToken?: string | null, password?: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/open-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, reveal, privacy_token: privacyToken, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Open file failed: ${res.statusText}`);
    }
    return res.json();
  },

  // ── V4 Persons API ─────────────────────────────────────────────────────────

  async listPersons(includeClusters = true, privacyToken?: string | null): Promise<Person[]> {
    const pToken = privacyToken ? `&privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/persons?include_clusters=${includeClusters}${pToken}`);
    if (!res.ok) throw new Error(`List persons failed: ${res.statusText}`);
    const data = await res.json();
    return data.persons || [];
  },

  async createPerson(
    name: string,
    aliases?: string[],
    referenceImagePaths?: string[],
    notes?: string
  ): Promise<{ status: string; person: Person }> {
    const res = await fetch(`${API_BASE}/api/persons`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        aliases,
        reference_image_paths: referenceImagePaths,
        notes,
      }),
    });
    if (!res.ok) throw new Error(`Create person failed: ${res.statusText}`);
    return res.json();
  },

  async getPersonDetails(personId: number, privacyToken?: string | null): Promise<PersonDetails> {
    const pToken = privacyToken ? `?privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/persons/${personId}${pToken}`);
    if (!res.ok) throw new Error(`Get person failed: ${res.statusText}`);
    return res.json();
  },

  async updatePerson(
    personId: number,
    data: { name?: string; notes?: string; aliases?: string[] }
  ): Promise<{ status: string; person: Person }> {
    const res = await fetch(`${API_BASE}/api/persons/${personId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Update person failed: ${res.statusText}`);
    return res.json();
  },

  async deletePerson(personId: number): Promise<{ status: string; id: number }> {
    const res = await fetch(`${API_BASE}/api/persons/${personId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`Delete person failed: ${res.statusText}`);
    return res.json();
  },

  async mergePersons(sourcePersonId: number, targetPersonId: number): Promise<{ status: string; person: Person }> {
    const res = await fetch(`${API_BASE}/api/persons/${sourcePersonId}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_person_id: targetPersonId }),
    });
    if (!res.ok) throw new Error(`Merge persons failed: ${res.statusText}`);
    return res.json();
  },

  async splitPerson(
    personId: number,
    newPersonName: string,
    detectionIds?: number[],
    fileIds?: number[]
  ): Promise<{ status: string; person: Person }> {
    const res = await fetch(`${API_BASE}/api/persons/${personId}/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_person_name: newPersonName,
        detection_ids: detectionIds,
        file_ids: fileIds,
      }),
    });
    if (!res.ok) throw new Error(`Split person failed: ${res.statusText}`);
    return res.json();
  },

  async nameCluster(clusterId: number, name: string): Promise<{ status: string; person: Person }> {
    const res = await fetch(`${API_BASE}/api/persons/cluster/${clusterId}/name`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error(`Name cluster failed: ${res.statusText}`);
    return res.json();
  },

  // ── V4 Voice Search API ────────────────────────────────────────────────────

  async voiceSearch(audioBlob: Blob, privacyToken?: string | null): Promise<{ transcript: string; language: string }> {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    const pToken = privacyToken ? `?privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/voice-search${pToken}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Voice search failed: ${res.statusText}`);
    }
    return res.json();
  },

  // ── V4 Privacy Center API ──────────────────────────────────────────────────

  async getPrivacyStatus(privacyToken?: string | null): Promise<PrivacyStatus> {
    const pToken = privacyToken ? `?privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/privacy/status${pToken}`);
    if (!res.ok) throw new Error(`Privacy status failed: ${res.statusText}`);
    return res.json();
  },

  async setupPrivacy(password: string): Promise<{ status: string; recovery_key: string; token: string }> {
    const res = await fetch(`${API_BASE}/api/privacy/setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Privacy setup failed: ${res.statusText}`);
    }
    return res.json();
  },

  async verifyPrivacy(password: string): Promise<{ status: string; token: string; message: string }> {
    const res = await fetch(`${API_BASE}/api/privacy/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Password verification failed: ${res.statusText}`);
    }
    return res.json();
  },

  async recoverPrivacy(recoveryKey: string, newPassword: string): Promise<{ status: string; token: string; message: string }> {
    const res = await fetch(`${API_BASE}/api/privacy/recover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recovery_key: recoveryKey, new_password: newPassword }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Recovery failed: ${res.statusText}`);
    }
    return res.json();
  },

  async lockPrivacy(privacyToken?: string | null): Promise<{ status: string }> {
    const pToken = privacyToken ? `?privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/privacy/lock${pToken}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Lock failed: ${res.statusText}`);
    return res.json();
  },

  async getPrivacySettings(): Promise<PrivacySettings> {
    const res = await fetch(`${API_BASE}/api/privacy/settings`);
    if (!res.ok) throw new Error(`Get privacy settings failed: ${res.statusText}`);
    return res.json();
  },

  async updatePrivacySettings(settings: PrivacySettings): Promise<{ status: string; settings: PrivacySettings }> {
    const res = await fetch(`${API_BASE}/api/privacy/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings }),
    });
    if (!res.ok) throw new Error(`Update privacy settings failed: ${res.statusText}`);
    return res.json();
  },

  async updateFilePrivacy(
    fileId: number,
    privacyState: string,
    privacyToken?: string | null
  ): Promise<{ status: string; file_id: number; privacy_state: string }> {
    const res = await fetch(`${API_BASE}/api/files/${fileId}/privacy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ privacy_state: privacyState, privacy_token: privacyToken }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Update file privacy failed: ${res.statusText}`);
    }
    return res.json();
  },

  async getStorageAnalytics(privacyToken?: string | null): Promise<StorageAnalytics> {
    const pToken = privacyToken ? `?privacy_token=${encodeURIComponent(privacyToken)}` : '';
    const res = await fetch(`${API_BASE}/api/storage-analytics${pToken}`);
    if (!res.ok) throw new Error(`Get storage analytics failed: ${res.statusText}`);
    return res.json();
  },

  async scanLibraryFaces(force = false): Promise<{
    status: string;
    images_scanned: number;
    faces_detected: number;
    new_clusters_created: number;
    total_persons: number;
    message?: string;
  }> {
    const res = await fetch(`${API_BASE}/api/persons/scan-faces?force=${force}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Scan faces failed: ${res.statusText}`);
    return res.json();
  },

  async applyPrivacyPolicies(): Promise<{ status: string; classified_counts: Record<string, number> }> {
    const res = await fetch(`${API_BASE}/api/privacy/apply-policies`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Apply privacy policies failed: ${res.statusText}`);
    return res.json();
  },

  getFaceCropUrl(detectionId: number): string {
    return `${API_BASE}/api/face-detections/${detectionId}/crop`;
  },

  getFileThumbnailUrl(fileId: number, size = 1400): string {
    return `${API_BASE}/api/thumbnail/${fileId}?size=${size}`;
  },

  async getFaceReviewQueue(limit = 150): Promise<{ review_queue: FaceReviewItem[] }> {
    const res = await fetch(`${API_BASE}/api/face-detections/review?limit=${limit}`);
    if (!res.ok) throw new Error(`Get face review queue failed: ${res.statusText}`);
    return res.json();
  },

  async getFileFaces(fileId: number): Promise<{ file_id: number; image_width: number; image_height: number; path?: string; faces: FileFaceDetection[] }> {
    const res = await fetch(`${API_BASE}/api/files/${fileId}/faces`);
    if (!res.ok) throw new Error(`Get file faces failed: ${res.statusText}`);
    return res.json();
  },

  async confirmAllFaceDetections(personId?: number): Promise<{ status: string; confirmed_count: number }> {
    const url = personId != null
      ? `${API_BASE}/api/face-detections/confirm-all?person_id=${personId}`
      : `${API_BASE}/api/face-detections/confirm-all`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error(`Confirm all failed: ${res.statusText}`);
    return res.json();
  },

  async createPersonFromDetection(
    detectionId: number,
    name: string,
    aliases?: string[],
    notes?: string
  ): Promise<{ status: string; person_id: number; name: string; detection_id: number }> {
    const res = await fetch(`${API_BASE}/api/face-detections/${detectionId}/create-person`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, aliases, notes }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Create person from detection failed: ${res.statusText}`);
    }
    return res.json();
  },

  async assignFaceDetection(
    detectionId: number,
    personId: number
  ): Promise<{ status: string; detection_id: number; person_id: number }> {
    const res = await fetch(`${API_BASE}/api/face-detections/${detectionId}/assign?person_id=${personId}`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Assign face failed: ${res.statusText}`);
    }
    return res.json();
  },

  async confirmFaceDetection(
    detectionId: number,
    personId?: number
  ): Promise<{ status: string; detection_id: number; person_id: number; person_name?: string }> {
    const url = personId != null
      ? `${API_BASE}/api/face-detections/${detectionId}/confirm?person_id=${personId}`
      : `${API_BASE}/api/face-detections/${detectionId}/confirm`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: personId != null ? JSON.stringify({ person_id: personId }) : undefined,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Confirm face failed: ${res.statusText}`);
    }
    return res.json();
  },

  async rejectFaceDetection(detectionId: number): Promise<{ status: string; detection_id: number }> {
    const res = await fetch(`${API_BASE}/api/face-detections/${detectionId}/reject`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Reject face failed: ${res.statusText}`);
    }
    return res.json();
  },

  async keepUnknownFaceDetection(detectionId: number): Promise<{ status: string; detection_id: number }> {
    const res = await fetch(`${API_BASE}/api/face-detections/${detectionId}/keep-unknown`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Keep unknown failed: ${res.statusText}`);
    }
    return res.json();
  },

  async addReferencePhoto(
    personId: number,
    photoPath?: string,
    detectionId?: number
  ): Promise<{ status: string; person_id: number; embedding_id?: number; file_id?: number; face_quality?: number }> {
    const res = await fetch(`${API_BASE}/api/persons/${personId}/reference-photos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ photo_path: photoPath, detection_id: detectionId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Add reference photo failed: ${res.statusText}`);
    }
    return res.json();
  },
};


