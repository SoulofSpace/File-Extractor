import React from 'react';
import { ShieldCheck, Cpu, Sliders, Database, CheckCircle2 } from 'lucide-react';
import { SystemStatus } from '../../api/types';

interface SettingsDialogProps {
  systemStatus: SystemStatus | null;
  animationEnabled: boolean;
  onToggleAnimation: () => void;
  cursorTrailEnabled?: boolean;
  onToggleCursorTrail?: () => void;
  defaultViewMode: 'grid' | 'list';
  onChangeDefaultView: (mode: 'grid' | 'list') => void;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({
  systemStatus,
  animationEnabled,
  onToggleAnimation,
  cursorTrailEnabled = true,
  onToggleCursorTrail,
  defaultViewMode,
  onChangeDefaultView,
}) => {
  return (
    <div className="w-full max-w-4xl mx-auto space-y-8 p-4 select-none">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Settings & System Info</h2>
        <p className="text-xs text-zinc-400 mt-1">
          Configure application preferences, UI behavior, and monitor local AI models.
        </p>
      </div>

      {/* 1. AI Models & Privacy */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-sky-400" />
          Local AI Model Pipeline (100% Offline)
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <span className="text-zinc-500 text-[11px] font-medium uppercase">Dense Embeddings</span>
            <div className="text-sm font-semibold text-white">all-MiniLM-L6-v2</div>
            <div className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
              <CheckCircle2 className="w-3 h-3" />
              <span>Loaded & Active (PyTorch)</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <span className="text-zinc-500 text-[11px] font-medium uppercase">Visual Vision Model</span>
            <div className="text-sm font-semibold text-white">clip-ViT-B-32</div>
            <div className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
              <CheckCircle2 className="w-3 h-3" />
              <span>Loaded & Active (OpenAI)</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <span className="text-zinc-500 text-[11px] font-medium uppercase">Document Understanding</span>
            <div className="text-sm font-semibold text-white">Qwen3.5-4B (VLM)</div>
            <div className="flex items-center gap-1 text-[11px] text-sky-400 font-medium">
              <CheckCircle2 className="w-3 h-3" />
              <span>Local llama.cpp Bridge</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>
            Privacy Guarantee: All neural vectors, embeddings, and OCR runs strictly on this device. Zero network sockets open to the cloud.
          </span>
        </div>
      </div>

      {/* 2. Appearance & UI Preferences */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Sliders className="w-3.5 h-3.5 text-indigo-400" />
          Interface Preferences
        </h3>

        <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] divide-y divide-white/[0.04]">
          {/* Water Canvas Animation Toggle */}
          <div className="flex items-center justify-between p-4">
            <div>
              <span className="text-sm font-semibold text-white block">Fluid Water Wave Animation</span>
              <span className="text-xs text-zinc-500 block mt-0.5">
                Renders GPU-accelerated water surface reflections and gentle wave physics on the home canvas.
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
                Spawns floating mini file-type tags (PDF, JPG, DOC, TXT, CODE) and stardust particles following mouse movement.
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
                Choose whether search results display as visual cards (Grid) or dense metadata rows (List).
              </span>
            </div>
            <div className="flex items-center gap-1 bg-white/[0.05] p-1 rounded-xl border border-white/[0.08]">
              <button
                type="button"
                onClick={() => onChangeDefaultView('grid')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  defaultViewMode === 'grid' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-400 hover:text-white'
                }`}
                style={defaultViewMode === 'grid' ? { backgroundColor: '#ffffff', color: '#09090b' } : {}}
              >
                Grid
              </button>
              <button
                type="button"
                onClick={() => onChangeDefaultView('list')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  defaultViewMode === 'list' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-400 hover:text-white'
                }`}
                style={defaultViewMode === 'list' ? { backgroundColor: '#ffffff', color: '#09090b' } : {}}
              >
                List
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Database & Storage Stats */}
      {systemStatus && (
        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-purple-400" />
            Database & Index Footprint
          </h3>

          <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-2 text-xs">
            <div className="flex justify-between py-1">
              <span className="text-zinc-400">Database Location:</span>
              <span className="font-mono text-zinc-200">{systemStatus.database_path}</span>
            </div>
            <div className="flex justify-between py-1 border-t border-white/[0.04]">
              <span className="text-zinc-400">Total Files Indexed:</span>
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
  );
};
