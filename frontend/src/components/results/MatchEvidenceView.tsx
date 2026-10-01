import React from 'react';
import { Eye, Brain, FileSearch, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';
import { MatchEvidence } from '../../api/types';

interface MatchEvidenceViewProps {
  evidence?: MatchEvidence;
  compact?: boolean;
}

const safeNum = (val: any): number => {
  if (typeof val === 'number') return isNaN(val) ? 0 : val;
  if (typeof val === 'string') {
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
  }
  return 0;
};

export const MatchEvidenceView: React.FC<MatchEvidenceViewProps> = ({ evidence, compact = false }) => {
  if (!evidence) return null;

  const clipScore = safeNum(evidence.CLIP ?? evidence.clip_similarity);
  const sbertScore = safeNum(evidence.SBERT ?? evidence.sbert_similarity);
  const bm25Score = safeNum(evidence.BM25 ?? evidence.bm25_score);
  const ocrScore = safeNum(evidence.OCR);
  const coordScore = safeNum(evidence.coordination ?? evidence.coordination_score);
  const contraPenalty = safeNum(evidence.contradiction ?? evidence.contradiction_penalty);

  const subjectMatch = safeNum(evidence.subject_match);
  const attributeMatch = safeNum(evidence.attribute_match);
  const clothingMatch = safeNum(evidence.clothing_match);
  const objectMatch = safeNum(evidence.object_match);

  const hasCompositional =
    subjectMatch > 0 ||
    attributeMatch > 0 ||
    clothingMatch > 0 ||
    objectMatch > 0 ||
    coordScore > 0;

  if (compact) {
    return (
      <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-zinc-400">
        {clipScore > 0.25 && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 font-medium">
            <Eye className="w-2.5 h-2.5" /> Visual {(clipScore * 100).toFixed(0)}%
          </span>
        )}
        {sbertScore > 0.3 && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-medium">
            <Brain className="w-2.5 h-2.5" /> Semantic {(sbertScore * 100).toFixed(0)}%
          </span>
        )}
        {bm25Score > 0.1 && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
            <FileSearch className="w-2.5 h-2.5" /> Text Match
          </span>
        )}
        {coordScore > 0.3 && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 font-medium">
            <Sparkles className="w-2.5 h-2.5" /> Coordinated
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-white tracking-wide uppercase text-[11px] flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-sky-400" />
          Why This Matched (AI Reasoning)
        </span>
        {coordScore > 0 && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/25">
            Coordination: {(coordScore * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Compositional Tuple Roles */}
      {hasCompositional && (
        <div className="grid grid-cols-2 gap-1.5 py-1">
          {subjectMatch > 0 && (
            <div className="flex items-center justify-between px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-zinc-400">Subject</span>
              <span className="font-mono text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> {(subjectMatch * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {attributeMatch > 0 && (
            <div className="flex items-center justify-between px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-zinc-400">
                {evidence.bound_attribute_match ? 'Bound Attribute' : 'Ambient Color'}
              </span>
              <span className="font-mono text-sky-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> {(attributeMatch * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {clothingMatch > 0 && (
            <div className="flex items-center justify-between px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-zinc-400">Clothing/Outfit</span>
              <span className="font-mono text-purple-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> {(clothingMatch * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {objectMatch > 0 && (
            <div className="flex items-center justify-between px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-zinc-400">Target Object</span>
              <span className="font-mono text-amber-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> {(objectMatch * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>
      )}

      {/* Retrieval Channel Signals */}
      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-white/[0.05] text-[11px] font-mono">
        <div className="flex items-center justify-between text-zinc-400">
          <span>CLIP Vision:</span>
          <span className="text-zinc-200">{clipScore.toFixed(3)}</span>
        </div>
        <div className="flex items-center justify-between text-zinc-400">
          <span>SBERT Text:</span>
          <span className="text-zinc-200">{sbertScore.toFixed(3)}</span>
        </div>
        <div className="flex items-center justify-between text-zinc-400">
          <span>BM25 Lexical:</span>
          <span className="text-zinc-200">{bm25Score.toFixed(3)}</span>
        </div>
        {ocrScore > 0 && (
          <div className="flex items-center justify-between text-zinc-400">
            <span>OCR Signal:</span>
            <span className="text-zinc-200">{ocrScore.toFixed(3)}</span>
          </div>
        )}
      </div>

      {contraPenalty > 0 && (
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-[11px]">
          <AlertCircle className="w-3.5 h-3.5 text-red-400" />
          <span>Contradiction penalty applied: -{(contraPenalty * 100).toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
};
