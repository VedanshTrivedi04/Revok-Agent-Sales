"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, CheckCircle2, Copy, FileUp, KeyRound, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { fetchApi } from "../../lib/api/client";
import { handleApiErrorToast } from "../../lib/api/error";
import { queryKeys } from "../../lib/api/query-keys";
import type { components } from "../../lib/api/schema";
import { guessUsageMapping, parseCsvHeader } from "../../lib/onboarding/csv";

type ApiKeyCreated = components["schemas"]["ApiKeyCreatedOut"];
type CsvJob = components["schemas"]["CsvJobOut"];

const MAX_CSV_BYTES = 10 * 1024 * 1024;
const fieldClass =
  "w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500";

/** Create a usage-ingest key (shown once) with a ready-to-run example request. */
export function ApiKeyPanel({ onCreated }: { onCreated: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Usage ingest");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      fetchApi<ApiKeyCreated>("/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), scopes: ["ingest:usage"] }),
      }),
    onSuccess: (key) => {
      setCreated(key);
      void queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys() });
      onCreated();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const apiOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const curl = created
    ? `curl -X POST ${apiOrigin}/api/v1/ingest/usage \\
  -H "Authorization: Bearer ${created.key}" \\
  -H "Content-Type: application/json" \\
  -d '[{"account_key":"customer.com","account_key_type":"domain","period_start":"2026-10-05","granularity":"week","active_users":42,"seats_used":40,"logins":310}]'`
    : "";

  if (created) {
    return (
      <div className="space-y-3">
        <div className="p-3 rounded-xl border border-amber-300 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-950/30 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 dark:text-amber-300">
            <KeyRound className="w-3.5 h-3.5" /> Copy your key now. It is shown only once.
          </div>
          <div className="flex items-center justify-between gap-2 font-mono text-xs">
            <span className="break-all text-slate-900 dark:text-slate-100">{created.key}</span>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard?.writeText(created.key);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-300 dark:border-slate-600 text-[11px] cursor-pointer"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500">
          Send weekly (or daily) usage per customer. Rows are matched by domain, external id or HubSpot id.
        </p>
        <pre className="text-[11px] leading-relaxed p-3 rounded-xl bg-slate-900 text-slate-100 overflow-x-auto">{curl}</pre>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
      className="space-y-3"
    >
      <label htmlFor="key-name" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
        Key name
      </label>
      <input
        id="key-name"
        value={name}
        maxLength={80}
        onChange={(e) => setName(e.target.value)}
        className={fieldClass}
      />
      <button
        type="submit"
        disabled={create.isPending || !name.trim()}
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50 cursor-pointer"
      >
        {create.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <KeyRound className="w-3.5 h-3.5" />}
        Generate key
      </button>
    </form>
  );
}

const TARGETS: Array<{ key: string; label: string; required: boolean }> = [
  { key: "account_key", label: "Account (domain or id)", required: true },
  { key: "period_start", label: "Period start date", required: true },
  { key: "active_users", label: "Active users", required: true },
  { key: "seats_used", label: "Seats used", required: false },
  { key: "logins", label: "Logins", required: false },
];

/** CSV upload: pick a file, confirm the column mapping, import, then watch the job. */
export function CsvPanel({ onImported }: { onImported: () => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [keyType, setKeyType] = useState<"domain" | "external_id" | "hubspot_id">("domain");
  const [granularity, setGranularity] = useState<"day" | "week">("week");
  const [fileError, setFileError] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const pickFile = async (f: File | null) => {
    setFileError("");
    setJobId(null);
    setFile(null);
    setColumns([]);
    if (!f) return;
    if (f.size > MAX_CSV_BYTES) {
      setFileError("That file is larger than 10 MB. Split it and upload in parts.");
      return;
    }
    const header = parseCsvHeader(await f.slice(0, 65536).text());
    if (header.length === 0) {
      setFileError("Could not read a header row from this file.");
      return;
    }
    setFile(f);
    setColumns(header);
    setMapping(guessUsageMapping(header));
  };

  const upload = useMutation({
    mutationFn: () => {
      const body = new FormData();
      body.append("file", file as File);
      body.append(
        "mapping",
        JSON.stringify({
          account_key: mapping.account_key,
          account_key_type: keyType,
          period_start: mapping.period_start,
          granularity,
          active_users: mapping.active_users,
          seats_used: mapping.seats_used || null,
          logins: mapping.logins || null,
        })
      );
      return fetchApi<CsvJob>("/ingest/usage/csv", { method: "POST", body });
    },
    onSuccess: (job) => setJobId(job.job_id),
    onError: (err) => handleApiErrorToast(err),
  });

  const job = useQuery<CsvJob>({
    queryKey: ["usage-csv-job", jobId],
    queryFn: () => fetchApi<CsvJob>(`/ingest/usage/csv/${jobId}`),
    enabled: jobId !== null,
    refetchInterval: (q) => (q.state.data && ["done", "failed"].includes(q.state.data.status) ? false : 1500),
  });

  const finished = job.data?.status === "done";
  React.useEffect(() => {
    if (finished) {
      toast.success("Usage import finished");
      void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
      onImported();
    }
  }, [finished, queryClient, onImported]);

  const ready = file !== null && TARGETS.filter((t) => t.required).every((t) => mapping[t.key]);

  return (
    <div className="space-y-4">
      <label
        htmlFor="usage-csv"
        className="flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed border-slate-300 dark:border-emerald-900 text-xs text-slate-500 cursor-pointer hover:border-emerald-500"
      >
        <FileUp className="w-5 h-5" />
        <span>{file ? file.name : "Choose a CSV file (up to 10 MB)"}</span>
        <input
          id="usage-csv"
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(e) => void pickFile(e.target.files?.[0] ?? null)}
        />
      </label>
      {fileError && (
        <p role="alert" className="text-xs text-rose-600 flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5" /> {fileError}
        </p>
      )}

      {file && !jobId && (
        <div className="space-y-3">
          {TARGETS.map((t) => (
            <div key={t.key} className="grid grid-cols-2 gap-2 items-center text-xs">
              <label htmlFor={`map-${t.key}`} className="font-semibold text-slate-700 dark:text-slate-300">
                {t.label}
                {t.required && <span className="text-rose-500"> *</span>}
              </label>
              <select
                id={`map-${t.key}`}
                value={mapping[t.key] ?? ""}
                onChange={(e) => setMapping({ ...mapping, [t.key]: e.target.value })}
                className={fieldClass}
              >
                <option value="">{t.required ? "Choose a column" : "Not in file"}</option>
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <div className="grid grid-cols-2 gap-2 items-center text-xs">
            <label htmlFor="key-type" className="font-semibold text-slate-700 dark:text-slate-300">
              Account column holds
            </label>
            <select id="key-type" value={keyType} onChange={(e) => setKeyType(e.target.value as typeof keyType)} className={fieldClass}>
              <option value="domain">Website domain</option>
              <option value="external_id">Your own account id</option>
              <option value="hubspot_id">HubSpot company id</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2 items-center text-xs">
            <label htmlFor="granularity" className="font-semibold text-slate-700 dark:text-slate-300">
              Each row covers one
            </label>
            <select id="granularity" value={granularity} onChange={(e) => setGranularity(e.target.value as typeof granularity)} className={fieldClass}>
              <option value="week">Week</option>
              <option value="day">Day</option>
            </select>
          </div>
          <button
            type="button"
            disabled={!ready || upload.isPending}
            onClick={() => upload.mutate()}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50 cursor-pointer"
          >
            {upload.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Import
          </button>
        </div>
      )}

      {jobId && (
        <div className="space-y-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 text-xs">
          {job.isLoading || !job.data ? (
            <span className="flex items-center gap-2 text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Starting import...
            </span>
          ) : (
            <>
              <div className="flex items-center gap-2 font-semibold">
                {job.data.status === "done" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                ) : job.data.status === "failed" ? (
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin text-slate-500" />
                )}
                <span className="capitalize">{job.data.status}</span>
                <span className="font-normal text-slate-500">
                  {job.data.accepted} accepted, {job.data.rejected_count} rejected of {job.data.processed} rows
                </span>
              </div>
              {job.data.errors.length > 0 && (
                <ul className="max-h-32 overflow-y-auto text-[11px] text-slate-500 space-y-0.5">
                  {job.data.errors.map((e) => (
                    <li key={e.index}>
                      Row {e.index + 1}: {e.reason.replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
