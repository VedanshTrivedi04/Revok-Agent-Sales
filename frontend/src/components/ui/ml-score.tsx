import React from "react";
import clsx from "clsx";
import { Activity, TrendingUp } from "lucide-react";
import type { components } from "../../lib/api/schema";
import { DateText } from "./date-text";

export type MlScores = components["schemas"]["MlScores"];
export type MlScore = components["schemas"]["MlScore"];
type Band = MlScore["band"];
type Kind = "churn" | "expansion";

const KIND_LABEL: Record<Kind, string> = { churn: "Churn risk", expansion: "Expansion chance" };
const BAND_LABEL: Record<Band, string> = { high: "High", medium: "Medium", low: "Low" };

// Text + icon + color (never color alone). A high expansion chance is good news, so it is green.
function bandClasses(kind: Kind, band: Band): string {
  if (band === "low") {
    return "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";
  }
  if (kind === "expansion") {
    return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
  }
  return band === "high"
    ? "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900/60"
    : "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/60";
}

export function formatProbability(p: number): string {
  return `${Math.round(p * 100)}%`;
}

interface MlScoreChipProps {
  kind: Kind;
  score: MlScore | null | undefined;
  className?: string;
}

/** Compact score for lists: "Churn risk 42% · Medium". Renders a dash when the account has no score. */
export function MlScoreChip({ kind, score, className }: MlScoreChipProps) {
  if (!score) return <span className="text-slate-400 font-mono text-[11px]">—</span>;
  const Icon = kind === "churn" ? Activity : TrendingUp;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border",
        bandClasses(kind, score.band),
        className
      )}
      role="status"
      aria-label={`${KIND_LABEL[kind]}: ${formatProbability(score.probability)}, ${BAND_LABEL[score.band]}`}
    >
      <Icon className="w-3 h-3 shrink-0" aria-hidden="true" />
      <span>{KIND_LABEL[kind]}</span>
      <span className="font-mono font-bold">{formatProbability(score.probability)}</span>
      <span aria-hidden="true">·</span>
      <span>{BAND_LABEL[score.band]}</span>
    </span>
  );
}

function ScoreBlock({ kind, score }: { kind: Kind; score: MlScore }) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{KIND_LABEL[kind]}</span>
        <MlScoreChip kind={kind} score={score} />
      </div>
      <div
        className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(score.probability * 100)}
        aria-label={KIND_LABEL[kind]}
      >
        <div
          className={clsx(
            "h-full rounded-full",
            score.band === "low"
              ? "bg-slate-400"
              : kind === "expansion"
              ? "bg-emerald-500"
              : score.band === "high"
              ? "bg-red-500"
              : "bg-amber-500"
          )}
          style={{ width: `${Math.max(2, Math.round(score.probability * 100))}%` }}
        />
      </div>
      {score.reasons.length > 0 && (
        <ul className="space-y-1">
          {score.reasons.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
              <span className="font-mono font-bold shrink-0" aria-hidden="true">
                {r.direction === "raises" ? "↑" : "↓"}
              </span>
              <span>
                <span className="sr-only">{r.direction === "raises" ? "Raises the score: " : "Lowers the score: "}</span>
                {r.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Full card for the account page: both scores, what drives them, and where the model comes from. */
export function MlScoresCard({ scores, className }: { scores: MlScores; className?: string }) {
  return (
    <div
      className={clsx(
        "rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-xs space-y-4",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
          Predicted risk and growth
        </h2>
        <span className="text-[10px] font-mono text-slate-400">
          Scored <DateText date={scores.scored_at} />
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ScoreBlock kind="churn" score={scores.churn} />
        <ScoreBlock kind="expansion" score={scores.expansion} />
      </div>
      <p className="text-[10px] text-slate-500 dark:text-slate-400 pt-3 border-t border-slate-100 dark:border-slate-800">
        {scores.synthetic
          ? "Estimate from a statistical model trained on synthetic data, not on this workspace's renewal history. Use it as a signal next to the evidence-based findings, not as a forecast."
          : "Estimate from a statistical model. Use it next to the evidence-based findings."}
        {scores.model_version ? ` Model ${scores.model_version}.` : ""}
      </p>
    </div>
  );
}
