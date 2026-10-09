import React, { useState, useEffect } from 'react';
import { ShieldCheck, Cpu, Sliders, Database, CheckCircle2, Lock, UserCheck, Mic, Globe } from 'lucide-react';
import { SystemStatus, PrivacySettings, PrivacyStatus } from '../../api/types';
import { apiClient } from '../../api/client';
import { PasswordModal } from '../common/PasswordModal';

interface SettingsDialogProps {
  systemStatus: SystemStatus | null;
  animationEnabled: boolean;
  onToggleAnimation: () => void;
  cursorTrailEnabled?: boolean;
  onToggleCursorTrail?: () => void;
  defaultViewMode: 'grid' | 'list';
  onChangeDefaultView: (mode: 'grid' | 'list') => void;
  privacyToken?: string | null;
  onPrivacyUnlocked?: (token: string) => void;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({
  systemStatus,
  animationEnabled,
  onToggleAnimation,
  cursorTrailEnabled = true,
  onToggleCursorTrail,
  defaultViewMode,
  onChangeDefaultView,
  privacyToken,
  onPrivacyUnlocked,
}) => {
  const [activeTab, setActiveTab] = useState<'general' | 'ai' | 'privacy'>('general');
  const [privacySettings, setPrivacySettings] = useState<PrivacySettings>({});
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus>({ is_configured: false, is_unlocked: false });
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordModalMode, setPasswordModalMode] = useState<'setup' | 'verify' | 'recover'>('setup');
  const [privacyNotice, setPrivacyNotice] = useState('');

  useEffect(() => {
    apiClient.getPrivacySettings().then(setPrivacySettings).catch(() => {});
    apiClient.getPrivacyStatus(privacyToken).then(setPrivacyStatus).catch(() => {});
  }, [privacyToken]);

  const [isApplyingPolicies, setIsApplyingPolicies] = useState(false);

  const handleUpdateSetting = async (key: string, value: string) => {
    const updated = { ...privacySettings, [key]: value };
    setPrivacySettings(updated);
    try {
      const res = await apiClient.updatePrivacySettings(updated);
      const applied = (res as any).applied_counts;
      if (applied) {
        const protCount = (applied.ID_DOCUMENT || 0) + (applied.BANKING_FINANCE || 0) + (applied.CONFIDENTIAL || 0);
        setPrivacyNotice(`Policies updated: ${protCount} sensitive files protected`);
      } else {
        setPrivacyNotice('Settings updated');
      }
      setTimeout(() => setPrivacyNotice(''), 3000);
    } catch (err: any) {
      console.error('Failed to update privacy setting:', err);
    }
  };

  const handleApplyPoliciesNow = async () => {
    setIsApplyingPolicies(true);
    try {
      const res = await apiClient.applyPrivacyPolicies();
      const counts = res.classified_counts || {};
      const protCount = (counts.ID_DOCUMENT || 0) + (counts.BANKING_FINANCE || 0) + (counts.CONFIDENTIAL || 0);
      setPrivacyNotice(`Privacy scan complete: ${protCount} files protected (${counts.ID_DOCUMENT || 0} IDs, ${counts.BANKING_FINANCE || 0} Banking, ${counts.CONFIDENTIAL || 0} Confidential)`);
      setTimeout(() => setPrivacyNotice(''), 5000);
    } catch (err: any) {
      alert(err.message || 'Failed to scan files');
    } finally {
      setIsApplyingPolicies(false);
    }
  };

  const isCategoryProtected = (catKey: string) => {
    return privacySettings[catKey] === 'true' || privacySettings[catKey] === '1';
  };

  const toggleCategory = (catKey: string) => {
    const nextVal = isCategoryProtected(catKey) ? 'false' : 'true';
    handleUpdateSetting(catKey, nextVal);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6 p-4 select-none animate-fadeIn text-zinc-100">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-white/10">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Settings & Preferences</h2>
          <p className="text-xs text-zinc-400 mt-1">
            Configure application UI, offline AI models, and the V4 Privacy Center.
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex items-center bg-zinc-900 border border-white/10 rounded-xl p-1 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('general')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'general' ? 'bg-white/10 text-white font-medium' : 'text-zinc-400 hover:text-white'
            }`}
          >
            General
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('ai')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'ai' ? 'bg-white/10 text-white font-medium' : 'text-zinc-400 hover:text-white'
            }`}
          >
            AI Models
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('privacy')}
            className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
              activeTab === 'privacy' ? 'bg-emerald-500/20 text-emerald-300 font-medium border border-emerald-500/30' : 'text-zinc-400 hover:text-white'
            }`}
          >
            <Lock className="w-3 h-3" />
            <span>Privacy Center</span>
          </button>
        </div>
      </div>

      {privacyNotice && (
        <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{privacyNotice}</span>
        </div>
      )}

      {/* ── TAB 1: GENERAL & APPEARANCE ────────────────────────────────────── */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              Interface Preferences
            </h3>

            <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] divide-y divide-white/[0.04]">
              {/* Water Canvas Animation Toggle */}
              <div className="flex items-center justify-between p-4">
                <div>
                  <span className="text-sm font-semibold text-white block">Interactive Fluid Background</span>
                  <span className="text-xs text-zinc-500 block mt-0.5">
                    GPU-accelerated gradient fluid surface following mouse physics.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={onToggleAnimation}
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    animationEnabled ? 'bg-sky-500' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      animationEnabled ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Cursor File-Tag Trail Toggle */}
              <div className="flex items-center justify-between p-4">
                <div>
                  <span className="text-sm font-semibold text-white block">File-Tag Cursor Trail Effect</span>
                  <span className="text-xs text-zinc-500 block mt-0.5">
                    Spawns floating mini file-type tags (PDF, JPG, DOC, TXT) following mouse movement.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={onToggleCursorTrail}
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    cursorTrailEnabled ? 'bg-sky-500' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      cursorTrailEnabled ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Default Search View Mode */}
              <div className="flex items-center justify-between p-4">
                <div>
                  <span className="text-sm font-semibold text-white block">Default Search Layout</span>
                  <span className="text-xs text-zinc-500 block mt-0.5">
                    Choose whether search results display as visual cards (Grid) or dense rows (List).
                  </span>
                </div>
                <div className="flex items-center gap-1 bg-white/[0.05] p-1 rounded-xl border border-white/[0.08]">
                  <button
                    type="button"
                    onClick={() => onChangeDefaultView('grid')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      defaultViewMode === 'grid' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    Grid
                  </button>
                  <button
                    type="button"
                    onClick={() => onChangeDefaultView('list')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      defaultViewMode === 'list' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    List
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Database stats */}
          {systemStatus && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-purple-400" />
                Database & Footprint
              </h3>

              <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-2 text-xs">
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Database Location:</span>
                  <span className="font-mono text-zinc-200">{systemStatus.database_path}</span>
                </div>
                <div className="flex justify-between py-1 border-t border-white/[0.04]">
                  <span className="text-zinc-400">Total Indexed Files:</span>
                  <span className="font-mono text-white font-semibold">{systemStatus.total_files.toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1 border-t border-white/[0.04]">
                  <span className="text-zinc-400">Monitored Folders:</span>
                  <span className="font-mono text-white">{systemStatus.folder_count}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: AI MODELS ──────────────────────────────────────────────── */}
      {activeTab === 'ai' && (
        <div className="space-y-6">
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-sky-400" />
              Local AI Engine (100% Offline)
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
                <span className="text-zinc-500 text-[11px] font-medium uppercase">Dense Embeddings</span>
                <div className="text-sm font-semibold text-white">all-MiniLM-L6-v2</div>
                <div className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>PyTorch SBERT Engine</span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
                <span className="text-zinc-500 text-[11px] font-medium uppercase">Visual Recognition</span>
                <div className="text-sm font-semibold text-white">clip-ViT-B-32</div>
                <div className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Zero-shot Visual Engine</span>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
                <span className="text-zinc-500 text-[11px] font-medium uppercase">Face Recognition (V4)</span>
                <div className="text-sm font-semibold text-white">YuNet + SFace (ONNX)</div>
                <div className="flex items-center gap-1 text-[11px] text-purple-400 font-medium">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>100% Local CPU/GPU</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>
                Zero Cloud Dependence: Embeddings, visual vectors, face descriptors, and OCR execute strictly locally.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: V4 PRIVACY CENTER ──────────────────────────────────────── */}
      {activeTab === 'privacy' && (
        <div className="space-y-6">
          {/* Master Password Section */}
          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                  <Lock className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white">Master Privacy Password (Argon2id)</h4>
                  <p className="text-xs text-zinc-400">
                    {privacyStatus.is_configured
                      ? 'Master password is configured. Protects sensitive documents and private mode.'
                      : 'Not configured yet. Create a password to protect financial and identity files.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {privacyStatus.is_configured ? (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        setPasswordModalMode('verify');
                        setShowPasswordModal(true);
                      }}
                      className="px-3.5 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-xs font-semibold rounded-xl border border-emerald-500/30 transition-colors"
                    >
                      {privacyStatus.is_unlocked ? 'Session Unlocked' : 'Unlock Session'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setPasswordModalMode('recover');
                        setShowPasswordModal(true);
                      }}
                      className="px-3 py-2 bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white text-xs font-medium rounded-xl transition-colors"
                    >
                      Reset Key
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setPasswordModalMode('setup');
                      setShowPasswordModal(true);
                    }}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-950/40 transition-all"
                  >
                    Setup Password
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Category Protection Toggles (Requirement 26) */}
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Category Auto-Protection Policies
                </h4>
                <p className="text-xs text-zinc-500">
                  When enabled, files automatically classified into these categories receive PROTECTED status.
                </p>
              </div>
              <button
                type="button"
                onClick={handleApplyPoliciesNow}
                disabled={isApplyingPolicies}
                className="px-3.5 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-xs font-semibold rounded-xl border border-emerald-500/30 transition-colors shrink-0"
              >
                {isApplyingPolicies ? 'Scanning...' : 'Scan & Protect Files Now'}
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { key: 'protect_banking', label: 'Banking & Finance', desc: 'Bank statements, passbooks, salary slips, IFSC/cards' },
                { key: 'protect_ids', label: 'IDs & Documents', desc: 'Aadhaar, PAN cards, passports, voter IDs, licenses' },
                { key: 'protect_personal_info', label: 'Personal Information', desc: 'Personal records, resumes, tax filings' },
                { key: 'protect_confidential', label: 'Confidential & Work', desc: 'NDAs, proprietary files, contract agreements' },
              ].map((item) => {
                const checked = isCategoryProtected(item.key);
                return (
                  <div
                    key={item.key}
                    onClick={() => toggleCategory(item.key)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start justify-between gap-3 ${
                      checked
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-white'
                        : 'bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:border-white/20'
                    }`}
                  >
                    <div>
                      <span className="text-xs font-semibold block">{item.label}</span>
                      <span className="text-[11px] text-zinc-500 block mt-0.5">{item.desc}</span>
                    </div>
                    <span className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                      checked ? 'bg-emerald-500 border-emerald-400 text-zinc-950 font-bold text-[10px]' : 'border-white/20'
                    }`}>
                      {checked ? '✓' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Privacy Display Settings (Requirement 37) */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Protected Content Display Policy
            </h4>

            <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] divide-y divide-white/[0.04]">
              {/* Filename hiding */}
              <div className="flex items-center justify-between p-4">
                <div>
                  <span className="text-sm font-semibold text-white block">Mask Protected Filenames</span>
                  <span className="text-xs text-zinc-500 block mt-0.5">
                    Replaces actual filename with "Protected Document" or "Protected Image" until unlocked.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    handleUpdateSetting(
                      'hide_protected_filename',
                      privacySettings.hide_protected_filename === 'true' ? 'false' : 'true'
                    )
                  }
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    privacySettings.hide_protected_filename === 'true' ? 'bg-emerald-500' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      privacySettings.hide_protected_filename === 'true' ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Image preview blur vs hide */}
              <div className="flex items-center justify-between p-4">
                <div>
                  <span className="text-sm font-semibold text-white block">Protected Image Previews</span>
                  <span className="text-xs text-zinc-500 block mt-0.5">
                    How protected photos are displayed in search results before unlocking.
                  </span>
                </div>
                <div className="flex items-center gap-1 bg-white/[0.05] p-1 rounded-xl border border-white/[0.08]">
                  <button
                    type="button"
                    onClick={() => handleUpdateSetting('protected_image_preview', 'blur')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      privacySettings.protected_image_preview !== 'hide'
                        ? 'bg-white text-zinc-950 shadow-sm'
                        : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    Blur
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUpdateSetting('protected_image_preview', 'hide')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      privacySettings.protected_image_preview === 'hide'
                        ? 'bg-white text-zinc-950 shadow-sm'
                        : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    Hide Completely
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* AI Features Toggles (Requirement 37) */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Neural Feature Toggles
            </h4>

            <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] divide-y divide-white/[0.04]">
              {/* Face indexing */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <UserCheck className="w-5 h-5 text-purple-400 shrink-0" />
                  <div>
                    <span className="text-sm font-semibold text-white block">Face Indexing & Person Clustering</span>
                    <span className="text-xs text-zinc-500 block mt-0.5">
                      Enable local face detection (YuNet) and embeddings (SFace) during folder scanning.
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    handleUpdateSetting(
                      'face_indexing_enabled',
                      privacySettings.face_indexing_enabled === 'false' ? 'true' : 'false'
                    )
                  }
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    privacySettings.face_indexing_enabled !== 'false' ? 'bg-purple-600' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      privacySettings.face_indexing_enabled !== 'false' ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Multilingual */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <Globe className="w-5 h-5 text-sky-400 shrink-0" />
                  <div>
                    <span className="text-sm font-semibold text-white block">Multilingual Indic & Code-Mixed Search</span>
                    <span className="text-xs text-zinc-500 block mt-0.5">
                      Translate Tamil, Hindi, and Hinglish queries via Sarvam Mayura v1 (never sends files).
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    handleUpdateSetting(
                      'multilingual_search_enabled',
                      privacySettings.multilingual_search_enabled === 'false' ? 'true' : 'false'
                    )
                  }
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    privacySettings.multilingual_search_enabled !== 'false' ? 'bg-sky-500' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      privacySettings.multilingual_search_enabled !== 'false' ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Voice search */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <Mic className="w-5 h-5 text-amber-400 shrink-0" />
                  <div>
                    <span className="text-sm font-semibold text-white block">Voice Search (Sarvam Saaras v4)</span>
                    <span className="text-xs text-zinc-500 block mt-0.5">
                      Direct speech-to-English translation for spoken natural language queries.
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    handleUpdateSetting(
                      'voice_search_enabled',
                      privacySettings.voice_search_enabled === 'false' ? 'true' : 'false'
                    )
                  }
                  className={`w-12 h-6 rounded-full transition-colors relative ${
                    privacySettings.voice_search_enabled !== 'false' ? 'bg-amber-500' : 'bg-white/10'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                      privacySettings.voice_search_enabled !== 'false' ? 'right-1' : 'left-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Password Modal */}
      <PasswordModal
        isOpen={showPasswordModal}
        mode={passwordModalMode}
        onClose={() => setShowPasswordModal(false)}
        onSuccess={(token) => {
          if (onPrivacyUnlocked) onPrivacyUnlocked(token);
          apiClient.getPrivacyStatus(token).then(setPrivacyStatus).catch(() => {});
        }}
      />
    </div>
  );
};
