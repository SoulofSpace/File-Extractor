import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Folder, Copy, Check, FileText, Brain } from 'lucide-react';
import { SearchResultItem, DocumentUnderstanding } from '../../api/types';
import { apiClient } from '../../api/client';
import { MatchEvidenceView } from '../results/MatchEvidenceView';

interface PreviewDrawerProps {
  file: SearchResultItem | null;
  onClose: () => void;
  onOpenFile: (path: string, reveal?: boolean) => void;
}

export const PreviewDrawer: React.FC<PreviewDrawerProps> = ({ file, onClose, onOpenFile }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'text' | 'ai'>('overview');
  const [detailedDocUnd, setDetailedDocUnd] = useState<DocumentUnderstanding | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!file) return;
    setDetailedDocUnd(null);
    apiClient
      .getFileDetail(file.file_id)
      .then((detail) => {
        if (detail.document_understanding) {
          setDetailedDocUnd(detail.document_understanding);
        }
      })
      .catch(() => {});
  }, [file?.file_id]);

  if (!file) return null;

  const ext = (file.extension || '').toLowerCase();
  const isImage = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(ext);

  const formatSize = (bytes?: number) => {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + (sizes[i] || 'B');
  };

  const formatDate = (dateVal?: string | number) => {
    if (!dateVal) return '—';
    try {
      const num = typeof dateVal === 'number' ? dateVal : parseFloat(String(dateVal));
      if (!isNaN(num) && num > 0) {
        const ms = num < 1e11 ? num * 1000 : num;
        return new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
      }
      const d = new Date(dateVal);
      if (isNaN(d.getTime())) return String(dateVal).slice(0, 10);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return String(dateVal).slice(0, 10);
    }
  };

  const copyPath = () => {
    if (file.path) {
      navigator.clipboard.writeText(file.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const previewText = file.ocr_text || file.extracted_text || file.snippet || '';

  return (
    <aside className="w-96 h-full flex flex-col bg-[#111216]/95 border-l border-white/[0.08] shadow-[-16px_0_40px_rgba(0,0,0,0.5)] backdrop-blur-2xl z-40 animate-in slide-in-from-right duration-200">
      {/* Top Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.08] bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-400 tracking-wider uppercase font-mono">
            Preview
          </span>
          <span className="px-2 py-0.5 rounded bg-white/[0.06] text-white text-[11px] font-mono font-medium">
            {ext.replace('.', '').toUpperCase() || 'FILE'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onOpenFile(file.path)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Open in default app"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
          <button
            onClick={() => onOpenFile(file.path, true)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Reveal in File Explorer"
          >
            <Folder className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors ml-1"
            title="Close Preview (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center px-5 border-b border-white/[0.06] bg-white/[0.01]">
        <button
          onClick={() => setActiveTab('overview')}
          className={`py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'overview'
              ? 'border-sky-400 text-white'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('text')}
          className={`py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'text'
              ? 'border-sky-400 text-white'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Content & OCR
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`py-2.5 px-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'ai'
              ? 'border-sky-400 text-white'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          AI Reasoning
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
        {activeTab === 'overview' && (
          <>
            {/* Visual Canvas / Thumbnail */}
            <div className="w-full h-52 rounded-2xl overflow-hidden bg-black/40 border border-white/[0.08] flex items-center justify-center relative">
              {isImage ? (
                <img
                  src={apiClient.getThumbnailUrl(file.file_id, 600)}
                  alt={file.filename}
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 p-6 text-center">
                  <div className="p-4 rounded-2xl bg-white/[0.05] border border-white/[0.08]">
                    <FileText className="w-8 h-8 text-zinc-400" />
                  </div>
                  <span className="font-semibold text-white text-sm">{file.category}</span>
                </div>
              )}
            </div>

            {/* Title & Path */}
            <div className="space-y-1">
              <h3 className="text-base font-bold text-white leading-snug break-words">
                {file.filename}
              </h3>
              <div className="flex items-center justify-between text-zinc-400 pt-1">
                <span className="font-mono text-[11px] truncate max-w-[240px]" title={file.path}>
                  {file.path}
                </span>
                <button
                  type="button"
                  onClick={copyPath}
                  className="p-1 rounded hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
                  title="Copy full path"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Quick Metadata Table */}
            <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] divide-y divide-white/[0.04]">
              <div className="flex justify-between px-3.5 py-2.5">
                <span className="text-zinc-500 font-medium">File Size</span>
                <span className="font-mono text-zinc-200">{formatSize(file.size_bytes)}</span>
              </div>
              <div className="flex justify-between px-3.5 py-2.5">
                <span className="text-zinc-500 font-medium">Category</span>
                <span className="text-zinc-200 font-medium">{file.category || (file as any).file_type || 'File'}</span>
              </div>
              <div className="flex justify-between px-3.5 py-2.5">
                <span className="text-zinc-500 font-medium">Date Modified</span>
                <span className="text-zinc-200">{formatDate(file.modified_at)}</span>
              </div>
              <div className="flex justify-between px-3.5 py-2.5">
                <span className="text-zinc-500 font-medium">Relevance Score</span>
                <span className="font-mono text-sky-400 font-bold">
                  {(file.relevance_score * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Primary Action Buttons */}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => onOpenFile(file.path)}
                className="flex-1 py-2.5 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-colors flex items-center justify-center gap-2 shadow-lg"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open File</span>
              </button>
              <button
                type="button"
                onClick={() => onOpenFile(file.path, true)}
                className="py-2.5 px-3 rounded-xl bg-white/[0.08] text-white font-medium hover:bg-white/[0.12] transition-colors border border-white/[0.1] flex items-center justify-center gap-1.5"
                title="Show in Folder"
              >
                <Folder className="w-3.5 h-3.5" />
                <span>Folder</span>
              </button>
            </div>
          </>
        )}

        {activeTab === 'text' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white">Extracted Text & OCR</span>
              {previewText && (
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(previewText);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copied' : 'Copy Text'}</span>
                </button>
              )}
            </div>

            {previewText ? (
              <div className="p-3.5 rounded-xl bg-black/50 border border-white/[0.08] font-mono text-xs leading-relaxed text-zinc-300 max-h-96 overflow-y-auto whitespace-pre-wrap select-text">
                {previewText}
              </div>
            ) : (
              <div className="p-8 text-center text-zinc-500 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                No text content or OCR extracted for this file.
              </div>
            )}
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="space-y-4">
            {/* Structured 15-Field MatchEvidence */}
            <MatchEvidenceView evidence={file.match_evidence} />

            {/* Qwen Document Understanding (if available) */}
            {detailedDocUnd && (
              <div className="space-y-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.08]">
                <span className="font-semibold text-white tracking-wide uppercase text-[11px] flex items-center gap-1.5">
                  <Brain className="w-3.5 h-3.5 text-purple-400" />
                  Qwen3.5 VLM Insights
                </span>

                {detailedDocUnd.description && (
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase font-bold">Summary</span>
                    <p className="text-zinc-200 mt-0.5 leading-relaxed">{detailedDocUnd.description}</p>
                  </div>
                )}

                {detailedDocUnd.visual_concepts && detailedDocUnd.visual_concepts.length > 0 && (
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase font-bold mb-1.5">Visual Concepts</span>
                    <div className="flex flex-wrap gap-1">
                      {detailedDocUnd.visual_concepts.map((c, i) => (
                        <span key={i} className="px-2 py-0.5 rounded-md bg-purple-500/15 text-purple-200 border border-purple-500/25 text-[10px]">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {detailedDocUnd.primary_objects && detailedDocUnd.primary_objects.length > 0 && (
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase font-bold mb-1.5">Objects Detected</span>
                    <div className="flex flex-wrap gap-1">
                      {detailedDocUnd.primary_objects.map((o, i) => (
                        <span key={i} className="px-2 py-0.5 rounded-md bg-white/[0.06] text-zinc-300 border border-white/[0.08] text-[10px]">
                          {o}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
