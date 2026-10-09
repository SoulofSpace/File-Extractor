import React, { useState, useEffect } from 'react';
import { FigmaIcon } from '../common/FigmaIcon';
import { apiClient } from '../../api/client';
import { Person, PersonDetails, FaceReviewItem, FileFaceDetection } from '../../api/types';

interface PersonsViewProps {
  privacyToken: string | null;
  onSearchPerson: (personName: string) => void;
  onOpenFile: (path: string) => void;
}

export const PersonsView: React.FC<PersonsViewProps> = ({
  privacyToken,
  onSearchPerson,
  onOpenFile,
}) => {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  // Default to 'review' as requested by the user
  const [activeTab, setActiveTab] = useState<'review' | 'known' | 'clusters'>('review');

  // Review Queue state
  const [reviewQueue, setReviewQueue] = useState<FaceReviewItem[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);

  // Photo Face Inspector Modal state
  const [inspectPhotoFileId, setInspectPhotoFileId] = useState<number | null>(null);
  const [inspectPhotoFilename, setInspectPhotoFilename] = useState<string>('');
  const [inspectPhotoPath, setInspectPhotoPath] = useState<string>('');
  const [inspectPhotoFaces, setInspectPhotoFaces] = useState<FileFaceDetection[]>([]);
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | null>(null);
  const [imgDimensions, setImgDimensions] = useState<{ width: number; height: number }>({ width: 0, height: 0 });
  const [photoLoading, setPhotoLoading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [confirmingAll, setConfirmingAll] = useState(false);

  // Modals & Drawers state
  const [selectedPerson, setSelectedPerson] = useState<PersonDetails | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState<Person | null>(null);
  const [showSplitModal, setShowSplitModal] = useState<PersonDetails | null>(null);
  const [showNameClusterModal, setShowNameClusterModal] = useState<Person | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showAddRefModal, setShowAddRefModal] = useState<PersonDetails | null>(null);

  // Form & Action states for individual detections
  const [createFromDet, setCreateFromDet] = useState<FaceReviewItem | FileFaceDetection | null>(null);
  const [createDetName, setCreateDetName] = useState('');
  const [createDetAliases, setCreateDetAliases] = useState('');
  const [createDetNotes, setCreateDetNotes] = useState('');

  const [assignFromDet, setAssignFromDet] = useState<FaceReviewItem | FileFaceDetection | null>(null);
  const [assignTargetPersonId, setAssignTargetPersonId] = useState<number | ''>('');

  const [addRefPhotoPath, setAddRefPhotoPath] = useState('');
  const [addRefFeedback, setAddRefFeedback] = useState('');

  // Scan faces state
  const [isScanningFaces, setIsScanningFaces] = useState(false);
  const [scanNotice, setScanNotice] = useState('');

  // General Form states
  const [newName, setNewName] = useState('');
  const [newAliases, setNewAliases] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [refPhotos, setRefPhotos] = useState<string>('');
  const [mergeTargetId, setMergeTargetId] = useState<number | ''>('');
  const [splitNewName, setSplitNewName] = useState('');
  const [splitSelectedFiles, setSplitSelectedFiles] = useState<number[]>([]);
  const [clusterName, setClusterName] = useState('');
  const [editPersonId, setEditPersonId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editAliases, setEditAliases] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [actionError, setActionError] = useState('');

  const loadPersons = async () => {
    setLoading(true);
    try {
      const data = await apiClient.listPersons(true, privacyToken);
      setPersons(data);
    } catch (err: any) {
      console.error('Failed to load persons:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadReviewQueue = async () => {
    setReviewLoading(true);
    try {
      const data = await apiClient.getFaceReviewQueue(200);
      setReviewQueue(data.review_queue || []);
    } catch (err: any) {
      console.error('Failed to load review queue:', err);
    } finally {
      setReviewLoading(false);
    }
  };

  useEffect(() => {
    loadPersons();
    loadReviewQueue();
  }, [privacyToken]);

  // Global key listener for Escape key to close any active modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (inspectPhotoFileId !== null) setInspectPhotoFileId(null);
        else if (selectedPerson !== null) setSelectedPerson(null);
        else if (createFromDet !== null) setCreateFromDet(null);
        else if (assignFromDet !== null) setAssignFromDet(null);
        else if (showAddRefModal !== null) setShowAddRefModal(null);
        else if (showNameClusterModal !== null) setShowNameClusterModal(null);
        else if (showAddModal) setShowAddModal(false);
        else if (showEditModal) setShowEditModal(false);
        else if (showMergeModal !== null) setShowMergeModal(null);
        else if (showSplitModal !== null) setShowSplitModal(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    inspectPhotoFileId,
    selectedPerson,
    createFromDet,
    assignFromDet,
    showAddRefModal,
    showNameClusterModal,
    showAddModal,
    showEditModal,
    showMergeModal,
    showSplitModal,
  ]);

  const handleOpenProfile = async (person: Person) => {
    try {
      const details = await apiClient.getPersonDetails(person.id, privacyToken);
      setSelectedPerson(details);
    } catch (err: any) {
      console.error('Failed to get person details:', err);
    }
  };

  const handleCreatePerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setActionError('');
    try {
      const aliasesList = newAliases.split(',').map((s) => s.trim()).filter(Boolean);
      const photoPaths = refPhotos.split('\n').map((s) => s.trim()).filter(Boolean);
      await apiClient.createPerson(newName.trim(), aliasesList, photoPaths, newNotes.trim());
      setShowAddModal(false);
      setNewName('');
      setNewAliases('');
      setNewNotes('');
      setRefPhotos('');
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      setActionError(err.message || 'Failed to create person');
    }
  };

  const handleNameCluster = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showNameClusterModal || !clusterName.trim()) return;
    setActionError('');
    try {
      await apiClient.nameCluster(showNameClusterModal.id, clusterName.trim());
      setShowNameClusterModal(null);
      setClusterName('');
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      setActionError(err.message || 'Failed to name cluster');
    }
  };

  const handleMerge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showMergeModal || !mergeTargetId) return;
    setActionError('');
    try {
      await apiClient.mergePersons(showMergeModal.id, Number(mergeTargetId));
      setShowMergeModal(null);
      setMergeTargetId('');
      if (selectedPerson?.id === showMergeModal.id) setSelectedPerson(null);
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      setActionError(err.message || 'Failed to merge persons');
    }
  };

  const handleSplit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showSplitModal || !splitNewName.trim()) return;
    setActionError('');
    try {
      await apiClient.splitPerson(showSplitModal.id, splitNewName.trim(), undefined, splitSelectedFiles);
      setShowSplitModal(null);
      setSplitNewName('');
      setSplitSelectedFiles([]);
      loadPersons();
      handleOpenProfile(showSplitModal);
    } catch (err: any) {
      setActionError(err.message || 'Failed to split person');
    }
  };

  const handleDeletePerson = async (personId: number) => {
    if (!confirm('Are you sure you want to delete this person profile? All original photos and files will be kept safe.')) {
      return;
    }
    try {
      await apiClient.deletePerson(personId);
      if (selectedPerson?.id === personId) setSelectedPerson(null);
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to delete person');
    }
  };

  const handleScanFaces = async () => {
    setIsScanningFaces(true);
    setScanNotice('Analyzing library photos with local YuNet & SFace models...');
    try {
      const res = await apiClient.scanLibraryFaces();
      setScanNotice(`Face scan completed: ${res.faces_detected} faces detected, ${res.new_clusters_created} new clusters created.`);
      setTimeout(() => setScanNotice(''), 4500);
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      setScanNotice(err.message || 'Face scanning failed');
      setTimeout(() => setScanNotice(''), 4500);
    } finally {
      setIsScanningFaces(false);
    }
  };

  const handleUpdatePerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editPersonId || !editName.trim()) return;
    setActionError('');
    try {
      const aliasesList = editAliases.split(',').map((s) => s.trim()).filter(Boolean);
      await apiClient.updatePerson(editPersonId, {
        name: editName.trim(),
        aliases: aliasesList,
        notes: editNotes.trim(),
      });
      setShowEditModal(false);
      loadPersons();
      const updated = await apiClient.getPersonDetails(editPersonId, privacyToken);
      setSelectedPerson(updated);
    } catch (err: any) {
      setActionError(err.message || 'Failed to update person');
    }
  };

  // ── Open Photo Inspector Action ───────────────────────────────────────────
  const handleOpenPhotoInspector = async (fileId: number, filename: string, initialDetId?: number, filePath?: string) => {
    if (!fileId) return;
    setInspectPhotoFileId(fileId);
    setInspectPhotoFilename(filename || 'Photograph');
    setInspectPhotoPath(filePath || '');
    setSelectedDetectionId(initialDetId || null);
    setImgDimensions({ width: 0, height: 0 });
    setPhotoLoading(true);
    setPhotoError(null);
    try {
      const res = await apiClient.getFileFaces(fileId);
      const facesList = res.faces || [];
      setInspectPhotoFaces(facesList);
      if (res.path && !filePath) {
        setInspectPhotoPath(res.path);
      }
      if (initialDetId) {
        setSelectedDetectionId(initialDetId);
      } else if (facesList.length > 0) {
        setSelectedDetectionId(facesList[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load file faces:', err);
      setPhotoError(err.message || 'Failed to load face detection data');
    }
  };

  const handleConfirmAllMatches = async () => {
    setConfirmingAll(true);
    try {
      await apiClient.confirmAllFaceDetections();
      loadPersons();
      loadReviewQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to auto-link and confirm matches');
    } finally {
      setConfirmingAll(false);
    }
  };

  const refreshInspectPhotoFaces = async (fileId: number, preserveDetId?: number) => {
    if (!fileId) return;
    try {
      const res = await apiClient.getFileFaces(fileId);
      setInspectPhotoFaces(res.faces || []);
      if (preserveDetId) {
        setSelectedDetectionId(preserveDetId);
      }
    } catch (err) {
      console.error('Failed to refresh faces:', err);
    }
  };

  const handleConfirmMatch = async (detectionId: number, suggestedPersonId?: number | null) => {
    try {
      await apiClient.confirmFaceDetection(detectionId, suggestedPersonId ?? undefined);
      setReviewQueue((prev) => prev.filter((item) => item.id !== detectionId));
      loadPersons();
      if (inspectPhotoFileId) {
        refreshInspectPhotoFaces(inspectPhotoFileId, detectionId);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to confirm match');
    }
  };

  const handleRejectMatch = async (detectionId: number) => {
    try {
      await apiClient.rejectFaceDetection(detectionId);
      setReviewQueue((prev) =>
        prev.map((item) =>
          item.id === detectionId
            ? { ...item, person_id: null, person_name: null, suggested_person_name: null, suggested_person_id: null }
            : item
        )
      );
      loadPersons();
      if (inspectPhotoFileId) {
        refreshInspectPhotoFaces(inspectPhotoFileId, detectionId);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to reject match');
    }
  };

  const handleKeepUnknown = async (detectionId: number) => {
    try {
      await apiClient.keepUnknownFaceDetection(detectionId);
      setReviewQueue((prev) => prev.filter((item) => item.id !== detectionId));
      if (inspectPhotoFileId) {
        refreshInspectPhotoFaces(inspectPhotoFileId, detectionId);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to keep unknown');
    }
  };

  const handleCreatePersonFromDetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createFromDet || !createDetName.trim()) return;
    try {
      const aliasesList = createDetAliases.split(',').map((s) => s.trim()).filter(Boolean);
      await apiClient.createPersonFromDetection(
        createFromDet.id,
        createDetName.trim(),
        aliasesList,
        createDetNotes.trim()
      );
      setCreateFromDet(null);
      setCreateDetName('');
      setCreateDetAliases('');
      setCreateDetNotes('');
      loadPersons();
      loadReviewQueue();
      if (inspectPhotoFileId) {
        refreshInspectPhotoFaces(inspectPhotoFileId, createFromDet.id);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to create person from face');
    }
  };

  const handleAssignPersonToDetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignFromDet || !assignTargetPersonId) return;
    try {
      await apiClient.assignFaceDetection(assignFromDet.id, Number(assignTargetPersonId));
      setAssignFromDet(null);
      setAssignTargetPersonId('');
      loadPersons();
      loadReviewQueue();
      if (inspectPhotoFileId) {
        refreshInspectPhotoFaces(inspectPhotoFileId, assignFromDet.id);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to assign face to person');
    }
  };

  const handleAddRefPhotoSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showAddRefModal || !addRefPhotoPath.trim()) return;
    setAddRefFeedback('Scanning and adding reference embedding...');
    try {
      const res = await apiClient.addReferencePhoto(showAddRefModal.id, addRefPhotoPath.trim());
      setAddRefFeedback(`Reference photo successfully enrolled! Quality: ${res.face_quality ? Math.round(res.face_quality * 100) + '%' : 'Good'}`);
      setAddRefPhotoPath('');
      loadPersons();
      const updated = await apiClient.getPersonDetails(showAddRefModal.id, privacyToken);
      setSelectedPerson(updated);
      setTimeout(() => setAddRefFeedback(''), 3000);
    } catch (err: any) {
      setAddRefFeedback(err.message || 'Failed to enrol reference photo');
    }
  };

  // Avatar renderer: uses the CROPPED face if available, otherwise falls back to file thumbnail
  const renderPersonAvatar = (p: Person | PersonDetails, size = 160) => {
    if (p.primary_face_detection_id) {
      return (
        <img
          src={apiClient.getFaceCropUrl(p.primary_face_detection_id)}
          alt={p.name}
          className="w-full h-full object-cover"
          onError={(e) => {
            if (p.avatar_file_id) {
              (e.target as HTMLImageElement).src = apiClient.getThumbnailUrl(p.avatar_file_id, size);
            } else {
              (e.target as HTMLElement).style.display = 'none';
            }
          }}
        />
      );
    }
    if (p.avatar_file_id) {
      return (
        <img
          src={apiClient.getThumbnailUrl(p.avatar_file_id, size)}
          alt={p.name}
          className="w-full h-full object-cover"
          onError={(e) => {
            (e.target as HTMLElement).style.display = 'none';
          }}
        />
      );
    }
    return (
      <div className="text-zinc-500">
        <FigmaIcon name="person" size={size > 160 ? 32 : 24} />
      </div>
    );
  };

  const knownPersons = persons.filter((p) => !p.is_cluster);
  const unknownClusters = persons.filter((p) => p.is_cluster);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fadeIn text-zinc-100">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <FigmaIcon name="person" size={20} />
            </span>
            <h2 className="text-xl font-bold tracking-tight text-white">Persons & Face Recognition</h2>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Local YuNet & SFace neural recognition. Review detected faces, enrol identities, and manage photo associations offline.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Tabs: Review & Unknown comes FIRST as requested */}
          <div className="flex items-center bg-zinc-900 border border-white/10 rounded-xl p-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('review')}
              className={`px-3.5 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === 'review' ? 'bg-white/10 text-white font-semibold' : 'text-zinc-400 hover:text-white'
              }`}
            >
              <span>Review & Unknown</span>
              {reviewQueue.length > 0 && (
                <span className="px-1.5 py-0.2 bg-purple-500/20 text-purple-300 font-bold rounded-full text-[10px] border border-purple-500/30">
                  {reviewQueue.length}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('known')}
              className={`px-3.5 py-1.5 rounded-lg transition-colors ${
                activeTab === 'known' ? 'bg-white/10 text-white font-semibold' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Assigned People ({knownPersons.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('clusters')}
              className={`px-3.5 py-1.5 rounded-lg transition-colors ${
                activeTab === 'clusters' ? 'bg-white/10 text-white font-semibold' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Face Clusters ({unknownClusters.length})
            </button>
          </div>

          <button
            type="button"
            onClick={handleScanFaces}
            disabled={isScanningFaces}
            className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl transition-all border ${
              isScanningFaces
                ? 'bg-purple-950/60 text-purple-300 border-purple-500/30 animate-pulse'
                : 'bg-white/[0.06] hover:bg-white/[0.12] text-white border-white/[0.1]'
            }`}
            title="Detect and cluster faces across all library images"
          >
            <FigmaIcon name="search" size={13} />
            <span>{isScanningFaces ? 'Scanning...' : 'Scan Library Faces'}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-purple-950/40 transition-all"
          >
            <FigmaIcon name="plus" size={15} />
            <span>Add Person</span>
          </button>
        </div>
      </div>

      {scanNotice && (
        <div className="p-3 bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs rounded-xl flex items-center justify-between animate-fadeIn">
          <span>{scanNotice}</span>
          <button type="button" onClick={() => setScanNotice('')} className="text-zinc-400 hover:text-white">✕</button>
        </div>
      )}

      {/* ── Active Tab Content ───────────────────────────────────────────── */}
      {activeTab === 'review' && (
        /* ── SECTION 1: Unknown Faces / Review Section (First) ── */
        <div className="space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between bg-zinc-900/40 border border-white/[0.06] p-4 rounded-2xl">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Detected Face Instances for Review</span>
                <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-bold border border-purple-500/30">
                  {reviewQueue.length} faces
                </span>
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Each card shows the exact cropped face. Confirm suggested matches, create new identities, or click "Open Photo" to view group context.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleConfirmAllMatches}
                disabled={confirmingAll || reviewLoading}
                className="px-3.5 py-1.5 bg-emerald-600/90 hover:bg-emerald-500 text-xs font-bold text-black rounded-xl transition-all flex items-center gap-1.5 shadow-lg shadow-emerald-950/40"
                title="Automatically link matching faces across photos for all known profiles"
              >
                <span>{confirmingAll ? 'Linking...' : '✓ Auto-Link & Confirm All'}</span>
              </button>
              <button
                type="button"
                onClick={loadReviewQueue}
                disabled={reviewLoading}
                className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-xs text-zinc-300 rounded-xl transition-colors"
              >
                {reviewLoading ? 'Refreshing...' : 'Refresh Queue'}
              </button>
            </div>
          </div>

          {reviewLoading ? (
            <div className="py-20 text-center text-zinc-500 text-sm">Loading detected faces...</div>
          ) : reviewQueue.length === 0 ? (
            <div className="py-20 text-center space-y-3 bg-zinc-900/20 rounded-2xl border border-white/[0.04]">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-zinc-900 border border-white/10 flex items-center justify-center text-emerald-400">
                <FigmaIcon name="check" size={24} />
              </div>
              <p className="text-sm font-bold text-white">Review Queue is Clear</p>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                All detected faces have been confirmed or assigned to identities. Click "Scan Library Faces" to detect more faces across your photos.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {reviewQueue.map((item) => (
                <div
                  key={item.id}
                  className="group relative bg-zinc-900/70 hover:bg-zinc-900 border border-white/[0.08] hover:border-purple-500/30 rounded-2xl p-4 transition-all duration-200 flex flex-col justify-between"
                >
                  <div>
                    {/* Face Crop Preview with overlay info */}
                    <div className="relative w-full aspect-square rounded-xl overflow-hidden bg-zinc-800/80 border border-white/10 mb-3 flex items-center justify-center">
                      <img
                        src={apiClient.getFaceCropUrl(item.id)}
                        alt={`Face #${item.id}`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      <div className="absolute top-2 left-2 flex items-center gap-1">
                        <span className="px-2 py-0.5 rounded-md bg-black/75 backdrop-blur-md text-[10px] font-bold text-white border border-white/10">
                          Face #{item.id}
                        </span>
                        {item.face_quality != null && (
                          <span
                            className="px-1.5 py-0.5 rounded-md bg-emerald-500/80 backdrop-blur-md text-[10px] font-bold text-black"
                            title="Face Quality Score"
                          >
                            {Math.round(item.face_quality * 100)}% Q
                          </span>
                        )}
                      </div>
                      {item.confidence != null && (
                        <div className="absolute top-2 right-2">
                          <span
                            className="px-1.5 py-0.5 rounded-md bg-black/75 backdrop-blur-md text-[10px] font-medium text-zinc-300 border border-white/10"
                            title="Detection Confidence"
                          >
                            {Math.round(item.confidence * 100)}% Conf
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Source File Info */}
                    <div className="mb-3">
                      <p className="text-xs font-semibold text-zinc-200 truncate" title={item.filename}>
                        {item.filename}
                      </p>
                      <p className="text-[10px] text-zinc-500 truncate mt-0.5" title={item.path}>
                        {item.path}
                      </p>
                    </div>

                    {/* Candidate Suggestion / Current Identity Banner */}
                    {item.suggested_person_name ? (
                      <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 mb-3">
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="text-purple-300 font-medium">Suggested Identity:</span>
                          {item.suggested_similarity != null && (
                            <span className="text-purple-400 font-bold">
                              {Math.round(item.suggested_similarity * 100)}% match
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-bold text-white truncate mb-2">{item.suggested_person_name}</p>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleConfirmMatch(item.id, item.suggested_person_id || item.person_id)}
                            className="flex-1 py-1 bg-emerald-600 hover:bg-emerald-500 text-black text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1"
                          >
                            <span>Confirm</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRejectMatch(item.id)}
                            className="flex-1 py-1 bg-white/10 hover:bg-white/20 text-zinc-300 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1"
                          >
                            <span>Reject</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="p-2.5 rounded-xl bg-zinc-800/50 border border-white/[0.06] mb-3">
                        <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-2">
                          <span>Unassigned Face</span>
                          <span className="text-[10px] text-zinc-500">No match</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setCreateFromDet(item);
                              setCreateDetName('');
                              setCreateDetAliases('');
                              setCreateDetNotes('');
                            }}
                            className="flex-1 py-1 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition-colors text-center"
                          >
                            Create Person
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setAssignFromDet(item);
                              setAssignTargetPersonId('');
                            }}
                            className="flex-1 py-1 bg-white/10 hover:bg-white/20 text-zinc-300 text-xs font-medium rounded-lg transition-colors text-center"
                          >
                            Assign
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Card Bottom Actions */}
                  <div className="flex items-center gap-1.5 pt-2 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={() => handleOpenPhotoInspector(item.file_id, item.filename, item.id, item.path)}
                      className="flex-1 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1"
                      title="Open full photo and inspect detected faces"
                    >
                      <FigmaIcon name="search" size={12} />
                      <span>Open Photo</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleKeepUnknown(item.id)}
                      className="px-2.5 py-1.5 bg-white/[0.04] hover:bg-white/10 text-zinc-400 hover:text-white text-xs rounded-lg transition-colors"
                      title="Keep as unassigned / unknown"
                    >
                      Keep Unknown
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'known' && (
        /* ── SECTION 2: Assigned People (Known identities) ── */
        <div className="space-y-4 animate-fadeIn">
          {loading ? (
            <div className="py-20 text-center text-zinc-500 text-sm">Loading people...</div>
          ) : knownPersons.length === 0 ? (
            <div className="py-20 text-center space-y-3 bg-zinc-900/20 rounded-2xl border border-white/[0.04]">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-zinc-900 border border-white/10 flex items-center justify-center text-zinc-500">
                <FigmaIcon name="person" size={24} />
              </div>
              <p className="text-sm font-bold text-white">No Assigned People Yet</p>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                Go to the "Review & Unknown" tab to name faces or click "Add Person" with reference photos.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {knownPersons.map((p) => (
                <div
                  key={p.id}
                  className="group relative bg-zinc-900/60 hover:bg-zinc-900 border border-white/[0.08] hover:border-purple-500/30 rounded-2xl p-4 transition-all duration-200 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center gap-3.5 mb-3">
                      {/* Avatar preview using CROPPED FACE */}
                      <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-zinc-800 border border-white/10 flex-shrink-0 flex items-center justify-center">
                        {renderPersonAvatar(p, 160)}
                      </div>

                      <div className="min-w-0 flex-1">
                        <h4 className="text-sm font-bold text-white truncate group-hover:text-purple-300 transition-colors">
                          {p.name}
                        </h4>
                        <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                          {p.aliases && p.aliases.length > 0 ? `aka ${p.aliases.join(', ')}` : 'Known Person'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-zinc-500 mb-3">
                      <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06]">
                        {(p as any).photo_count != null
                          ? `${(p as any).photo_count} photos · ${(p as any).doc_count || 0} docs`
                          : `${p.file_count || (p as any).total_files_count || 0} files`}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 pt-2 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={() => handleOpenProfile(p)}
                      className="flex-1 py-1.5 bg-white/[0.06] hover:bg-white/10 text-white text-xs font-medium rounded-lg transition-colors text-center"
                    >
                      View Profile
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowMergeModal(p);
                        setMergeTargetId('');
                      }}
                      className="px-2.5 py-1.5 text-zinc-400 hover:text-white hover:bg-white/[0.06] rounded-lg text-xs transition-colors"
                      title="Merge identity with another person"
                    >
                      Merge
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'clusters' && (
        /* ── SECTION 3: Face Clusters ── */
        <div className="space-y-4 animate-fadeIn">
          {loading ? (
            <div className="py-20 text-center text-zinc-500 text-sm">Loading clusters...</div>
          ) : unknownClusters.length === 0 ? (
            <div className="py-20 text-center space-y-3 bg-zinc-900/20 rounded-2xl border border-white/[0.04]">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-zinc-900 border border-white/10 flex items-center justify-center text-zinc-500">
                <FigmaIcon name="person" size={24} />
              </div>
              <p className="text-sm font-bold text-white">No Unnamed Face Clusters</p>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                All detected faces have been either identified or remain in the review queue.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {unknownClusters.map((p) => (
                <div
                  key={p.id}
                  className="group relative bg-zinc-900/60 hover:bg-zinc-900 border border-white/[0.08] hover:border-amber-500/30 rounded-2xl p-4 transition-all duration-200 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center gap-3.5 mb-3">
                      {/* Avatar preview using CROPPED FACE of this cluster */}
                      <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-zinc-800 border-2 border-amber-500/40 flex-shrink-0 flex items-center justify-center">
                        {renderPersonAvatar(p, 160)}
                        <span className="absolute bottom-0 right-0 w-3 h-3 bg-amber-400 rounded-full border-2 border-zinc-900" title="Unidentified Cluster" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <h4 className="text-sm font-bold text-white truncate group-hover:text-amber-300 transition-colors">
                          {p.name}
                        </h4>
                        <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                          {p.primary_face_detection_id ? `Face #${p.primary_face_detection_id}` : 'Unidentified Cluster'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-zinc-500 mb-3">
                      <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06]">
                        {(p as any).photo_count != null
                          ? `${(p as any).photo_count} photos · ${(p as any).doc_count || 0} docs`
                          : `${p.file_count || (p as any).total_files_count || 0} files`}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 pt-2 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={() => handleOpenProfile(p)}
                      className="flex-1 py-1.5 bg-white/[0.06] hover:bg-white/10 text-white text-xs font-medium rounded-lg transition-colors text-center"
                      title="View recognized faces in this cluster"
                    >
                      Photos
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowNameClusterModal(p);
                        setClusterName('');
                      }}
                      className="flex-1 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-semibold rounded-lg border border-amber-500/30 transition-colors flex items-center justify-center gap-1"
                    >
                      <span>Name</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Photo Face Inspector Modal (Open Photo Action) ──────────────── */}
      {inspectPhotoFileId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6 bg-black/85 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            // Dismiss when clicking the backdrop
            if (e.target === e.currentTarget) setInspectPhotoFileId(null);
          }}
        >
          <div className="w-full max-w-6xl max-h-[92vh] bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-zinc-950/70 flex-shrink-0">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  <FigmaIcon name="search" size={18} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-bold text-white truncate">{inspectPhotoFilename}</h3>
                  <p className="text-xs text-zinc-400 flex items-center gap-2">
                    <span>{inspectPhotoFaces.length} face{inspectPhotoFaces.length === 1 ? '' : 's'} detected in this image</span>
                    <span>•</span>
                    <span className="text-emerald-400">Independent Face ID targeting</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {inspectPhotoPath && (
                  <button
                    type="button"
                    onClick={() => onOpenFile(inspectPhotoPath)}
                    className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow"
                    title="Open full image file in Windows default viewer"
                  >
                    <FigmaIcon name="file" size={13} />
                    <span>Open in OS</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setInspectPhotoFileId(null)}
                  className="px-3.5 py-1.5 bg-white/10 hover:bg-rose-500/25 text-white hover:text-rose-200 border border-white/20 hover:border-rose-500/40 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-lg"
                  title="Close Photo Inspector (Esc)"
                >
                  ✕ <span>Close</span>
                </button>
              </div>
            </div>

            {/* Main Body: Photo on Left, Inspector on Right */}
            <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
              {/* Photo Container */}
              <div className="flex-1 bg-black/75 p-4 flex flex-col items-center justify-center overflow-auto relative select-none min-h-[320px]">
                {photoLoading && !photoError && (
                  <div className="flex flex-col items-center justify-center gap-3 text-zinc-400 py-16 animate-pulse">
                    <div className="w-8 h-8 rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
                    <span className="text-xs font-medium">Loading photograph preview...</span>
                  </div>
                )}

                {photoError ? (
                  <div className="max-w-md p-6 bg-zinc-900 border border-rose-500/30 rounded-2xl text-center space-y-3 shadow-2xl">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center font-bold text-lg">
                      !
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">Preview Unavailable</h4>
                      <p className="text-xs text-zinc-400 mt-1">
                        {photoError}. The image file may have been moved or requires the system viewer.
                      </p>
                      {inspectPhotoPath && (
                        <p className="text-[11px] font-mono text-zinc-400 mt-2 truncate bg-black/60 px-3 py-1.5 rounded-lg border border-white/10 select-all" title={inspectPhotoPath}>
                          {inspectPhotoPath}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center justify-center gap-2 pt-2">
                      {inspectPhotoPath && (
                        <button
                          type="button"
                          onClick={() => onOpenFile(inspectPhotoPath)}
                          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded-xl transition-colors shadow-lg"
                        >
                          Open with Default Viewer
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setPhotoError(null);
                          setPhotoLoading(true);
                        }}
                        className="px-3.5 py-2 bg-white/10 hover:bg-white/20 text-zinc-300 text-xs font-medium rounded-xl transition-colors"
                      >
                        Retry
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={`relative inline-block max-w-full max-h-[68vh] ${photoLoading ? 'hidden' : 'block'}`}>
                    <img
                      src={apiClient.getFileThumbnailUrl(inspectPhotoFileId, 1600)}
                      alt={inspectPhotoFilename}
                      className="max-w-full max-h-[68vh] object-contain block rounded-lg shadow-2xl"
                      onLoad={(e) => {
                        setPhotoLoading(false);
                        setPhotoError(null);
                        setImgDimensions({
                          width: e.currentTarget.naturalWidth,
                          height: e.currentTarget.naturalHeight,
                        });
                      }}
                      onError={() => {
                        setPhotoLoading(false);
                        setPhotoError('Image file preview could not be streamed from disk');
                      }}
                    />

                    {/* Face Bounding Box Overlays */}
                    {!photoLoading &&
                      inspectPhotoFaces.map((f) => {
                        const isSelected = f.id === selectedDetectionId;
                        const leftPct = f.norm_x != null ? f.norm_x * 100 : (imgDimensions.width > 0 ? (f.box_x / imgDimensions.width) * 100 : 0);
                        const topPct = f.norm_y != null ? f.norm_y * 100 : (imgDimensions.height > 0 ? (f.box_y / imgDimensions.height) * 100 : 0);
                        const widthPct = f.norm_w != null ? f.norm_w * 100 : (imgDimensions.width > 0 ? (f.box_w / imgDimensions.width) * 100 : 0);
                        const heightPct = f.norm_h != null ? f.norm_h * 100 : (imgDimensions.height > 0 ? (f.box_h / imgDimensions.height) * 100 : 0);

                        return (
                          <div
                            key={f.id}
                            onClick={() => setSelectedDetectionId(f.id)}
                            style={{
                              left: `${leftPct}%`,
                              top: `${topPct}%`,
                              width: `${widthPct}%`,
                              height: `${heightPct}%`,
                            }}
                            className={`absolute transition-all duration-150 cursor-pointer rounded ${
                              isSelected
                                ? 'border-2 border-emerald-400 bg-emerald-500/25 shadow-[0_0_15px_rgba(16,185,129,0.5)] z-30 ring-2 ring-emerald-300/80'
                                : 'border-2 border-cyan-400/80 bg-cyan-500/10 hover:border-cyan-300 hover:bg-cyan-500/25 z-10'
                            }`}
                            title={`Click to select Face #${f.id} (${f.person_name || 'Unassigned'})`}
                          >
                            <div
                              className={`absolute -top-6 left-0 px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap shadow pointer-events-none transition-transform ${
                                isSelected
                                  ? 'bg-emerald-500 text-black scale-105 z-30'
                                  : 'bg-cyan-600/90 text-white z-10'
                              }`}
                            >
                              {isSelected
                                ? `✓ Face #${f.id} (Selected)`
                                : `Face #${f.id} • ${f.person_name || 'Unassigned'}`}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                )}

                {/* Bottom Face Strip Selector for Group Photos */}
                {inspectPhotoFaces.length > 1 && !photoError && (
                  <div className="w-full mt-3 pt-3 border-t border-white/10 flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
                    <span className="text-[11px] font-semibold text-zinc-400 whitespace-nowrap pl-1">
                      Faces ({inspectPhotoFaces.length}):
                    </span>
                    {inspectPhotoFaces.map((f) => {
                      const isSel = f.id === selectedDetectionId;
                      return (
                        <button
                          key={f.id}
                          type="button"
                          onClick={() => setSelectedDetectionId(f.id)}
                          className={`flex items-center gap-1.5 px-2 py-1 rounded-xl border text-[11px] transition-all flex-shrink-0 ${
                            isSel
                              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300 ring-1 ring-emerald-400'
                              : 'bg-zinc-900 border-white/10 text-zinc-400 hover:text-white hover:border-white/20'
                          }`}
                        >
                          <img
                            src={apiClient.getFaceCropUrl(f.id)}
                            alt={`Face #${f.id}`}
                            className="w-5 h-5 rounded-md object-cover"
                          />
                          <span className="font-medium">
                            #{f.id} {f.person_name ? `(${f.person_name})` : ''}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Selected Face Inspector Panel */}
              <div className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-white/10 p-5 bg-zinc-950/80 overflow-y-auto flex flex-col justify-between">
                {(() => {
                  const activeFace = inspectPhotoFaces.find((f) => f.id === selectedDetectionId) || inspectPhotoFaces[0];
                  if (!activeFace) {
                    return (
                      <div className="py-10 text-center text-zinc-500 text-xs">
                        No face detected or selected in this photo.
                      </div>
                    );
                  }

                  return (
                    <div className="space-y-4">
                      <div className="flex items-center gap-3">
                        <img
                          src={apiClient.getFaceCropUrl(activeFace.id)}
                          alt={`Face #${activeFace.id}`}
                          className="w-16 h-16 rounded-xl object-cover border-2 border-emerald-400 shadow-lg flex-shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold">
                              Face #{activeFace.id}
                            </span>
                          </div>
                          <p className="text-sm font-bold text-white truncate mt-1">
                            {activeFace.person_name || 'Unassigned Identity'}
                          </p>
                          <p className="text-[11px] text-zinc-400 truncate">
                            {activeFace.is_cluster ? 'In Unknown Cluster' : activeFace.person_name ? 'Known Person' : 'No Identity Linked'}
                          </p>
                        </div>
                      </div>

                      {/* Metrics */}
                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                          <span className="text-zinc-500 block">Quality</span>
                          <span className="text-white font-bold">
                            {activeFace.face_quality != null ? `${Math.round(activeFace.face_quality * 100)}%` : 'N/A'}
                          </span>
                        </div>
                        <div className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                          <span className="text-zinc-500 block">Confidence</span>
                          <span className="text-white font-bold">
                            {Math.round(activeFace.confidence * 100)}%
                          </span>
                        </div>
                      </div>

                      {/* Group photo notice */}
                      <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[11px] leading-relaxed">
                        <strong>Group photo isolation:</strong> Any naming or assignment applies strictly to <strong>Face #{activeFace.id}</strong>. Other faces in this photo will not be affected.
                      </div>

                      {/* Actions for this face */}
                      <div className="space-y-2 pt-2 border-t border-white/10">
                        <button
                          type="button"
                          onClick={() => {
                            setCreateFromDet(activeFace);
                            setCreateDetName('');
                            setCreateDetAliases('');
                            setCreateDetNotes('');
                          }}
                          className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl transition-colors shadow-lg shadow-purple-950/40 text-center"
                        >
                          Create Person from Face #{activeFace.id}
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setAssignFromDet(activeFace);
                            setAssignTargetPersonId('');
                          }}
                          className="w-full py-2 bg-white/10 hover:bg-white/15 text-zinc-200 text-xs font-semibold rounded-xl transition-colors text-center"
                        >
                          Assign to Existing Person
                        </button>

                        {(activeFace.person_name || activeFace.suggested_person_name) && (
                          <div className="space-y-2 pt-1">
                            {!activeFace.person_name && activeFace.suggested_person_name && (
                              <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs">
                                <span className="text-purple-300 font-medium">Suggested Identity: </span>
                                <span className="text-white font-bold">{activeFace.suggested_person_name}</span>
                                {activeFace.suggested_similarity != null && (
                                  <span className="text-purple-400 font-bold ml-1.5">
                                    ({Math.round(activeFace.suggested_similarity * 100)}% match)
                                  </span>
                                )}
                              </div>
                            )}
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleConfirmMatch(activeFace.id, activeFace.person_id || activeFace.suggested_person_id)}
                                className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-black text-xs font-bold rounded-lg transition-colors"
                              >
                                Confirm Match
                              </button>
                              <button
                                type="button"
                                onClick={() => handleRejectMatch(activeFace.id)}
                                className="flex-1 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-semibold rounded-lg transition-colors"
                              >
                                Unlink / Reject
                              </button>
                            </div>
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={() => handleKeepUnknown(activeFace.id)}
                          className="w-full py-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
                        >
                          Keep as Unknown
                        </button>
                      </div>

                      {/* Switch between faces in photo */}
                      {inspectPhotoFaces.length > 1 && (
                        <div className="pt-3 border-t border-white/10">
                          <span className="text-[11px] font-medium text-zinc-400 block mb-2">
                            All faces in this photo ({inspectPhotoFaces.length}):
                          </span>
                          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                            {inspectPhotoFaces.map((f) => (
                              <button
                                key={f.id}
                                type="button"
                                onClick={() => setSelectedDetectionId(f.id)}
                                className={`relative w-10 h-10 rounded-lg overflow-hidden border flex-shrink-0 transition-all ${
                                  f.id === selectedDetectionId
                                    ? 'border-emerald-400 ring-2 ring-emerald-400/50 scale-105'
                                    : 'border-white/10 opacity-70 hover:opacity-100'
                                }`}
                                title={`Select Face #${f.id}`}
                              >
                                <img
                                  src={apiClient.getFaceCropUrl(f.id)}
                                  alt={`Face #${f.id}`}
                                  className="w-full h-full object-cover"
                                />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Person Profile Drawer ────────────────────────────────────────── */}
      {selectedPerson && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedPerson(null);
          }}
        >
          <div className="w-full max-w-2xl bg-zinc-900 border-l border-white/10 h-full p-6 overflow-y-auto space-y-6 shadow-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between pb-4 border-b border-white/10">
                <div className="flex items-center gap-4">
                  {/* Drawer Avatar using CROPPED FACE */}
                  <div className="relative w-16 h-16 rounded-2xl overflow-hidden bg-zinc-800 border-2 border-purple-400/50 flex-shrink-0 flex items-center justify-center shadow-lg">
                    {renderPersonAvatar(selectedPerson, 240)}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">{selectedPerson.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-zinc-400">
                        {selectedPerson.is_cluster ? 'Auto-clustered Face Identity' : 'Confirmed Identity'}
                      </span>
                      {selectedPerson.primary_face_detection_id && (
                        <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                          Face #{selectedPerson.primary_face_detection_id}
                        </span>
                      )}
                      {selectedPerson.aliases && selectedPerson.aliases.length > 0 && (
                        <span className="text-xs text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
                          aka {selectedPerson.aliases.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {selectedPerson.is_cluster ? (
                    <button
                      type="button"
                      onClick={() => {
                        setShowNameClusterModal(selectedPerson);
                        setClusterName('');
                      }}
                      className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 text-xs font-bold rounded-xl flex items-center gap-1.5 transition-colors shadow-lg shadow-amber-950/30"
                    >
                      <span>Name This Person</span>
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setEditPersonId(selectedPerson.id);
                          setEditName(selectedPerson.name);
                          setEditAliases((selectedPerson.aliases || []).join(', '));
                          setEditNotes(selectedPerson.notes || '');
                          setShowEditModal(true);
                        }}
                        className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-medium rounded-xl transition-colors"
                      >
                        Edit Info
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setShowAddRefModal(selectedPerson);
                          setAddRefPhotoPath('');
                          setAddRefFeedback('');
                        }}
                        className="px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-medium rounded-xl transition-colors flex items-center gap-1"
                        title="Enrol additional reference photos for this person"
                      >
                        <FigmaIcon name="plus" size={12} />
                        <span>Add Reference Photo</span>
                      </button>
                    </>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      onSearchPerson(selectedPerson.name);
                      setSelectedPerson(null);
                    }}
                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors"
                  >
                    <FigmaIcon name="search" size={13} />
                    <span>Search Files</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSplitModal(selectedPerson)}
                    className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-medium rounded-xl transition-colors"
                  >
                    Split
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeletePerson(selectedPerson.id)}
                    className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-medium rounded-xl transition-colors"
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedPerson(null)}
                    className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition-colors ml-2"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {selectedPerson.notes && (
                <div className="p-3 bg-white/[0.02] border border-white/[0.06] rounded-xl text-xs text-zinc-300 mt-4">
                  {selectedPerson.notes}
                </div>
              )}

              {/* Linked Files Section */}
              <div className="space-y-3 mt-6">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                    Associated Files ({selectedPerson.files?.length || 0})
                  </h4>
                  <div className="flex items-center gap-3 text-xs text-zinc-500">
                    <span>{selectedPerson.photo_count || 0} photos</span>
                    <span>•</span>
                    <span>{selectedPerson.doc_count || 0} documents</span>
                  </div>
                </div>

                {(!selectedPerson.files || selectedPerson.files.length === 0) ? (
                  <div className="py-12 text-center text-zinc-500 text-xs">
                    No files currently linked to this identity.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedPerson.files.map((file) => {
                      const fileId = file.file_id || file.id;
                      const confPct = Math.round(((file.confidence ?? (file as any).link_confidence) || 1.0) * 100);
                      return (
                        <div
                          key={file.id || file.file_id}
                          className="group flex items-center justify-between p-3 rounded-xl bg-zinc-800/40 hover:bg-zinc-800 border border-white/[0.04] hover:border-white/10 transition-colors"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            {/* Image preview thumbnail */}
                            {['.jpg', '.jpeg', '.png', '.webp'].includes((file.extension || '').toLowerCase()) ? (
                              <div className="w-9 h-9 rounded-lg overflow-hidden bg-zinc-900 border border-white/10 flex-shrink-0">
                                <img
                                  src={apiClient.getThumbnailUrl(fileId, 120)}
                                  alt={file.filename}
                                  className="w-full h-full object-cover"
                                  onError={(e) => {
                                    (e.target as HTMLElement).style.display = 'none';
                                  }}
                                />
                              </div>
                            ) : (
                              <div className="w-9 h-9 rounded-lg bg-zinc-900 border border-white/10 flex items-center justify-center text-zinc-500 flex-shrink-0">
                                <FigmaIcon name="file" size={16} />
                              </div>
                            )}

                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-zinc-200 truncate group-hover:text-purple-300 transition-colors">
                                {file.filename}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
                                  {file.link_type} match
                                </span>
                                <span className="text-[10px] text-zinc-500">•</span>
                                <span className="text-[10px] text-purple-400 font-medium">
                                  {confPct}% confidence
                                </span>
                                {file.is_confirmed && (
                                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
                                    Confirmed
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 flex-shrink-0">
                            {['.jpg', '.jpeg', '.png', '.webp'].includes((file.extension || '').toLowerCase()) && (
                              <button
                                type="button"
                                onClick={() => handleOpenPhotoInspector(fileId, file.filename, selectedPerson.primary_face_detection_id || undefined, file.path)}
                                className="px-2.5 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-medium rounded-lg transition-colors flex items-center gap-1"
                                title="Inspect face bounding boxes"
                              >
                                <FigmaIcon name="search" size={11} />
                                <span>Inspect Faces</span>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => onOpenFile(file.path)}
                              className="px-2.5 py-1.5 bg-white/5 hover:bg-white/10 text-xs text-zinc-300 rounded-lg transition-colors"
                            >
                              Open
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="pt-4 border-t border-white/10 flex items-center justify-between text-xs text-zinc-500">
              <span>Local Profile ID: #{selectedPerson.id}</span>
              <button
                type="button"
                onClick={() => setSelectedPerson(null)}
                className="text-zinc-400 hover:text-white"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Add Person Profile Modal ─────────────────────────────────────── */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowAddModal(false);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Add Person Profile</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Enrol reference photos to train local SFace face recognition.
            </p>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleCreatePerson} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Full Name *</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Raghul"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={newAliases}
                  onChange={(e) => setNewAliases(e.target.value)}
                  placeholder="e.g. Rahul, Bro, Alex"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Reference Photo Paths (one per line)</label>
                <textarea
                  value={refPhotos}
                  onChange={(e) => setRefPhotos(e.target.value)}
                  placeholder="C:\Users\space\Photos\raghul_portrait.jpg"
                  rows={3}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                />
                <p className="text-[11px] text-zinc-500 mt-1">
                  Reference photos are embedded locally via SFace. Group photos are guarded: only clear, primary faces are enrolled.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Notes / Relationship</label>
                <input
                  type="text"
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  placeholder="e.g. Colleague, brother"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newName.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Create Person
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Create Person from Detection Modal ──────────────────────────── */}
      {createFromDet && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setCreateFromDet(null);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <div className="flex items-center gap-3 mb-4">
              <img
                src={apiClient.getFaceCropUrl(createFromDet.id)}
                alt={`Face #${createFromDet.id}`}
                className="w-14 h-14 rounded-xl object-cover border-2 border-purple-400"
              />
              <div>
                <h3 className="text-base font-bold text-white">Create Person from Face #{createFromDet.id}</h3>
                <p className="text-xs text-zinc-400">
                  This face embedding will become the primary reference photo.
                </p>
              </div>
            </div>

            <form onSubmit={handleCreatePersonFromDetSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Name *</label>
                <input
                  type="text"
                  value={createDetName}
                  onChange={(e) => setCreateDetName(e.target.value)}
                  placeholder="e.g. Raghul"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={createDetAliases}
                  onChange={(e) => setCreateDetAliases(e.target.value)}
                  placeholder="e.g. Rahul, Bro"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Notes / Info</label>
                <textarea
                  value={createDetNotes}
                  onChange={(e) => setCreateDetNotes(e.target.value)}
                  placeholder="Additional context or notes..."
                  rows={2}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateFromDet(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!createDetName.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Create Person
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Assign Existing Person to Face Modal ────────────────────────── */}
      {assignFromDet && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setAssignFromDet(null);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <div className="flex items-center gap-3 mb-4">
              <img
                src={apiClient.getFaceCropUrl(assignFromDet.id)}
                alt={`Face #${assignFromDet.id}`}
                className="w-14 h-14 rounded-xl object-cover border-2 border-blue-400"
              />
              <div>
                <h3 className="text-base font-bold text-white">Assign Face #{assignFromDet.id}</h3>
                <p className="text-xs text-zinc-400">
                  Select an existing known identity to link this face detection to.
                </p>
              </div>
            </div>

            <form onSubmit={handleAssignPersonToDetSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Select Person *</label>
                <select
                  value={assignTargetPersonId}
                  onChange={(e) => setAssignTargetPersonId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
                  required
                >
                  <option value="">Select a known person...</option>
                  {knownPersons.map((kp) => (
                    <option key={kp.id} value={kp.id}>
                      {kp.name} {kp.aliases && kp.aliases.length > 0 ? `(${kp.aliases.join(', ')})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAssignFromDet(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!assignTargetPersonId}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Assign Person
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Add Reference Photo Modal ────────────────────────────────────── */}
      {showAddRefModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowAddRefModal(null);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Add Reference Photo</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Add an additional reference photo for <strong>{showAddRefModal.name}</strong> to improve recognition across diverse poses and lighting.
            </p>

            {addRefFeedback && (
              <div className="p-2.5 mb-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs rounded-xl">
                {addRefFeedback}
              </div>
            )}

            <form onSubmit={handleAddRefPhotoSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Photo File Path *</label>
                <input
                  type="text"
                  value={addRefPhotoPath}
                  onChange={(e) => setAddRefPhotoPath(e.target.value)}
                  placeholder="C:\Users\...\portrait.jpg"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                  required
                  autoFocus
                />
                <p className="text-[11px] text-zinc-500 mt-1">
                  Path to an image containing a clear face. If multiple faces exist, the primary face will be selected.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddRefModal(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Done
                </button>
                <button
                  type="submit"
                  disabled={!addRefPhotoPath.trim()}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-black text-xs font-bold rounded-xl"
                >
                  Add Reference Photo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Name Face Cluster Modal (shows CROPPED FACE of that person!) ─── */}
      {showNameClusterModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowNameClusterModal(null);
          }}
        >
          <div className="w-full max-w-sm bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <div className="flex items-center gap-3.5 mb-4">
              <div className="w-14 h-14 rounded-xl overflow-hidden bg-zinc-800 border-2 border-amber-400 flex-shrink-0 flex items-center justify-center shadow-lg">
                {renderPersonAvatar(showNameClusterModal, 160)}
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-bold text-white">Name This Person</h3>
                <p className="text-xs text-zinc-400">
                  {showNameClusterModal.primary_face_detection_id
                    ? `Assign identity to Face #${showNameClusterModal.primary_face_detection_id}`
                    : `Assign identity to ${showNameClusterModal.name}`}
                </p>
              </div>
            </div>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleNameCluster} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Person Name *</label>
                <input
                  type="text"
                  value={clusterName}
                  onChange={(e) => setClusterName(e.target.value)}
                  placeholder="e.g. Arun Kumar"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-amber-500"
                  required
                  autoFocus
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowNameClusterModal(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!clusterName.trim()}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-zinc-950 text-xs font-bold rounded-xl shadow-lg shadow-amber-950/40"
                >
                  Save Person
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Merge Identities Modal ───────────────────────────────────────── */}
      {showMergeModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowMergeModal(null);
          }}
        >
          <div className="w-full max-w-sm bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Merge Person Profiles</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Merge all photos and embeddings of <strong>{showMergeModal.name}</strong> into another identity.
            </p>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleMerge} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Merge Into Target Person *</label>
                <select
                  value={mergeTargetId}
                  onChange={(e) => setMergeTargetId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                >
                  <option value="">Select target person...</option>
                  {persons
                    .filter((p) => p.id !== showMergeModal.id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} {p.is_cluster ? '(Cluster)' : ''}
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowMergeModal(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!mergeTargetId}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Confirm Merge
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Split Person Modal ───────────────────────────────────────────── */}
      {showSplitModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowSplitModal(null);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Split Identity Profile</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Separate selected photos from <strong>{showSplitModal.name}</strong> into a brand new person.
            </p>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleSplit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">New Person Name *</label>
                <input
                  type="text"
                  value={splitNewName}
                  onChange={(e) => setSplitNewName(e.target.value)}
                  placeholder="e.g. Senthil Kumar"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Select Files to Move to New Person</label>
                <div className="max-h-48 overflow-y-auto space-y-1.5 p-2 bg-black/40 border border-white/10 rounded-xl">
                  {showSplitModal.files?.map((f) => {
                    const fid = f.file_id || f.id;
                    return (
                      <label
                        key={fid}
                        className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-white/5 cursor-pointer text-xs"
                      >
                        <input
                          type="checkbox"
                          checked={splitSelectedFiles.includes(fid)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSplitSelectedFiles([...splitSelectedFiles, fid]);
                            } else {
                              setSplitSelectedFiles(splitSelectedFiles.filter((id) => id !== fid));
                            }
                          }}
                          className="rounded border-white/20 bg-zinc-800 text-purple-600 focus:ring-purple-500"
                        />
                        <span className="text-zinc-200 truncate">{f.filename}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowSplitModal(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!splitNewName.trim() || splitSelectedFiles.length === 0}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Create Separate Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Edit Person Identity Modal ───────────────────────────────────── */}
      {showEditModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowEditModal(false);
          }}
        >
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Edit Person Profile</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Update name, aliases, or background information for this identity.
            </p>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleUpdatePerson} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Name *</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={editAliases}
                  onChange={(e) => setEditAliases(e.target.value)}
                  placeholder="e.g. Bro, Alex, Shorty"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Notes / Info</label>
                <textarea
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  placeholder="Additional context or notes..."
                  rows={3}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!editName.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl"
                >
                  Save Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
