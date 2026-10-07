import React, { useState, useEffect } from 'react';
import { FigmaIcon } from '../common/FigmaIcon';
import { apiClient } from '../../api/client';
import { Person, PersonDetails } from '../../api/types';

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
  const [activeTab, setActiveTab] = useState<'all' | 'known' | 'clusters'>('all');

  // Modals & Drawers state
  const [selectedPerson, setSelectedPerson] = useState<PersonDetails | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState<Person | null>(null);
  const [showSplitModal, setShowSplitModal] = useState<PersonDetails | null>(null);
  const [showNameClusterModal, setShowNameClusterModal] = useState<Person | null>(null);

  // Form states
  const [newName, setNewName] = useState('');
  const [newAliases, setNewAliases] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [refPhotos, setRefPhotos] = useState<string>('');
  const [mergeTargetId, setMergeTargetId] = useState<number | ''>('');
  const [splitNewName, setSplitNewName] = useState('');
  const [splitSelectedFiles, setSplitSelectedFiles] = useState<number[]>([]);
  const [clusterName, setClusterName] = useState('');
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

  useEffect(() => {
    loadPersons();
  }, [privacyToken]);

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
    } catch (err: any) {
      alert(err.message || 'Failed to delete person');
    }
  };

  const knownPersons = persons.filter((p) => !p.is_cluster);
  const unknownClusters = persons.filter((p) => p.is_cluster);

  const displayedList =
    activeTab === 'known' ? knownPersons : activeTab === 'clusters' ? unknownClusters : persons;

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
            Local YuNet & SFace neural recognition. Manage identities, photos, and face clusters offline.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center bg-zinc-900 border border-white/10 rounded-xl p-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'all' ? 'bg-white/10 text-white font-medium' : 'text-zinc-400 hover:text-white'
              }`}
            >
              All ({persons.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('known')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'known' ? 'bg-white/10 text-white font-medium' : 'text-zinc-400 hover:text-white'
              }`}
            >
              People ({knownPersons.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('clusters')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'clusters' ? 'bg-white/10 text-white font-medium' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Unknown Clusters ({unknownClusters.length})
            </button>
          </div>

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

      {/* Grid of Persons / Clusters */}
      {loading ? (
        <div className="py-20 text-center text-zinc-500 text-sm">Loading people & face clusters...</div>
      ) : displayedList.length === 0 ? (
        <div className="py-20 text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-zinc-900 border border-white/10 flex items-center justify-center text-zinc-600">
            <FigmaIcon name="person" size={24} />
          </div>
          <p className="text-sm font-medium text-zinc-400">No identities found in this category</p>
          <p className="text-xs text-zinc-600 max-w-sm mx-auto">
            Click "Add Person" with reference photos to train local recognition, or scan image folders to auto-cluster faces.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {displayedList.map((p) => {
            const isCluster = p.is_cluster;
            return (
              <div
                key={p.id}
                className="group relative bg-zinc-900/60 hover:bg-zinc-900 border border-white/[0.08] hover:border-purple-500/30 rounded-2xl p-4 transition-all duration-200 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center gap-3.5 mb-3">
                    {/* Avatar preview */}
                    <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-zinc-800 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {p.avatar_file_id ? (
                        <img
                          src={apiClient.getThumbnailUrl(p.avatar_file_id, 160)}
                          alt={p.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="text-zinc-500">
                          <FigmaIcon name="person" size={24} />
                        </div>
                      )}
                      {isCluster && (
                        <span className="absolute bottom-0 right-0 w-3 h-3 bg-amber-400 rounded-full border-2 border-zinc-900" title="Unknown Face Cluster" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <h4 className="text-sm font-bold text-white truncate group-hover:text-purple-300 transition-colors">
                        {p.name}
                      </h4>
                      <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                        {isCluster ? 'Unidentified Cluster' : p.aliases && p.aliases.length > 0 ? `aka ${p.aliases.join(', ')}` : 'Known Person'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-[11px] text-zinc-500 mb-3">
                    <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06]">
                      {p.file_count || 0} associated files
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 pt-2 border-t border-white/[0.06]">
                  {isCluster ? (
                    <button
                      type="button"
                      onClick={() => {
                        setShowNameClusterModal(p);
                        setClusterName('');
                      }}
                      className="w-full py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-semibold rounded-lg border border-amber-500/30 transition-colors flex items-center justify-center gap-1"
                    >
                      <span>Name Person</span>
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => handleOpenProfile(p)}
                        className="flex-1 py-1.5 bg-white/[0.06] hover:bg-white/10 text-white text-xs font-medium rounded-lg transition-colors text-center"
                      >
                        Profile
                      </button>
                      <button
                        type="button"
                        onClick={() => onSearchPerson(p.name)}
                        className="p-1.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg border border-purple-500/20 transition-colors"
                        title="Search all files for this person"
                      >
                        <FigmaIcon name="search" size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowMergeModal(p)}
                        className="p-1.5 text-zinc-500 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
                        title="Merge with another person"
                      >
                        <FigmaIcon name="more" size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Person Profile Modal ────────────────────────────────────────── */}
      {selectedPerson && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="w-full max-w-3xl max-h-[90vh] bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-white/10 flex items-start justify-between bg-zinc-950/40">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-zinc-800 border border-white/10 overflow-hidden flex items-center justify-center">
                  {selectedPerson.avatar_file_id ? (
                    <img
                      src={apiClient.getThumbnailUrl(selectedPerson.avatar_file_id, 240)}
                      alt={selectedPerson.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <FigmaIcon name="person" size={32} />
                  )}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">{selectedPerson.name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-zinc-400">
                      {selectedPerson.photo_count} photos · {selectedPerson.doc_count} documents
                    </span>
                    {selectedPerson.aliases && selectedPerson.aliases.length > 0 && (
                      <span className="text-xs text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
                        aka {selectedPerson.aliases.join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
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
                  className="p-2 text-zinc-500 hover:text-rose-400 rounded-xl hover:bg-rose-500/10 transition-colors"
                  title="Delete person identity (files remain safe)"
                >
                  <FigmaIcon name="trash" size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPerson(null)}
                  className="p-2 text-zinc-500 hover:text-white rounded-xl hover:bg-white/5 transition-colors"
                >
                  <FigmaIcon name="close" size={16} />
                </button>
              </div>
            </div>

            {/* Content: Linked Files Gallery & List */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Linked Photos */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3 flex items-center gap-2">
                  <FigmaIcon name="gallery" size={14} />
                  <span>Recognized Photos ({selectedPerson.files.filter((f) => f.link_type === 'face').length})</span>
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3">
                  {selectedPerson.files
                    .filter((f) => f.link_type === 'face')
                    .map((file) => (
                      <div
                        key={file.id}
                        onClick={() => onOpenFile(file.path)}
                        className="group cursor-pointer rounded-xl overflow-hidden bg-zinc-950 border border-white/10 hover:border-purple-500 transition-all relative aspect-square"
                      >
                        <img
                          src={apiClient.getThumbnailUrl(file.file_id, 300)}
                          alt={file.filename}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                        />
                        <div className="absolute inset-x-0 bottom-0 p-1.5 bg-black/60 backdrop-blur-sm text-[10px] text-zinc-300 truncate">
                          {file.filename}
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Linked Documents (OCR / Filename / Entities) */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3 flex items-center gap-2">
                  <FigmaIcon name="file" size={14} />
                  <span>Linked Documents ({selectedPerson.files.filter((f) => f.link_type !== 'face').length})</span>
                </h4>
                <div className="space-y-2">
                  {selectedPerson.files
                    .filter((f) => f.link_type !== 'face')
                    .map((file) => (
                      <div
                        key={file.id}
                        onClick={() => onOpenFile(file.path)}
                        className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/60 hover:bg-zinc-800/60 border border-white/[0.06] hover:border-white/20 cursor-pointer transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <FigmaIcon name="file" size={16} />
                          <div className="truncate">
                            <p className="text-xs font-medium text-white truncate">{file.filename}</p>
                            <p className="text-[10px] text-zinc-500 truncate">{file.path}</p>
                          </div>
                        </div>
                        <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
                          Matched via {file.link_type.toUpperCase()}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Add Person Modal ────────────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="w-full max-w-lg bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-white mb-1">Add New Person</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Create an identity and train local face recognition embeddings from reference photos.
            </p>

            {actionError && (
              <div className="p-2.5 mb-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
                {actionError}
              </div>
            )}

            <form onSubmit={handleCreatePerson} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Person Name *</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Raghul, Priya, John Doe"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  autoFocus
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={newAliases}
                  onChange={(e) => setNewAliases(e.target.value)}
                  placeholder="e.g. Raghu, Bro, Rahul"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  Reference Photo Paths (one per line)
                </label>
                <textarea
                  value={refPhotos}
                  onChange={(e) => setRefPhotos(e.target.value)}
                  placeholder="C:\Users\...\photo1.jpg&#10;C:\Users\...\photo2.png"
                  rows={3}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs font-mono focus:outline-none focus:border-purple-500"
                />
                <p className="text-[10px] text-zinc-500 mt-1">
                  Local YuNet & SFace extract 128-d embeddings from these photos as ground truth identity anchors.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Notes</label>
                <input
                  type="text"
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  placeholder="Optional notes or relationship..."
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
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl"
                >
                  Create Identity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Name Cluster Modal ─────────────────────────────────────────── */}
      {showNameClusterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="w-full max-w-sm bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Name Unknown Person</h3>
            <p className="text-xs text-zinc-400 mb-3">
              Approve this face cluster into a named person profile.
            </p>

            <form onSubmit={handleNameCluster} className="space-y-3">
              <input
                type="text"
                value={clusterName}
                onChange={(e) => setClusterName(e.target.value)}
                placeholder="Enter person's name..."
                className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                autoFocus
                required
              />
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
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold text-xs rounded-xl"
                >
                  Confirm & Name
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Merge Modal ────────────────────────────────────────────────── */}
      {showMergeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Merge Person</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Merge all embeddings, photos, and linked files from <span className="text-white font-semibold">{showMergeModal.name}</span> into another person.
            </p>

            <form onSubmit={handleMerge} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Select Target Person</label>
                <select
                  value={mergeTargetId}
                  onChange={(e) => setMergeTargetId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                >
                  <option value="">-- Choose target person --</option>
                  {persons
                    .filter((p) => p.id !== showMergeModal.id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.is_cluster ? 'Cluster' : 'Person'})
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowMergeModal(null)}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl"
                >
                  Confirm Merge
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Split Modal ────────────────────────────────────────────────── */}
      {showSplitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="w-full max-w-lg bg-zinc-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Split Person</h3>
            <p className="text-xs text-zinc-400 mb-3">
              Move selected photos/files from <span className="text-white font-semibold">{showSplitModal.name}</span> into a new person.
            </p>

            <form onSubmit={handleSplit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">New Person Name *</label>
                <input
                  type="text"
                  value={splitNewName}
                  onChange={(e) => setSplitNewName(e.target.value)}
                  placeholder="Enter new identity name..."
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  Select Files to Move ({splitSelectedFiles.length} selected)
                </label>
                <div className="max-h-48 overflow-y-auto space-y-1.5 p-2 bg-black/40 rounded-xl border border-white/10">
                  {showSplitModal.files.map((f) => {
                    const isChecked = splitSelectedFiles.includes(f.file_id);
                    return (
                      <label
                        key={f.id}
                        className="flex items-center gap-2 p-1.5 hover:bg-white/5 rounded-lg cursor-pointer text-xs text-zinc-300"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSplitSelectedFiles([...splitSelectedFiles, f.file_id]);
                            } else {
                              setSplitSelectedFiles(splitSelectedFiles.filter((id) => id !== f.file_id));
                            }
                          }}
                          className="rounded border-white/20"
                        />
                        <span className="truncate">{f.filename}</span>
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
                  Split into New Person
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
