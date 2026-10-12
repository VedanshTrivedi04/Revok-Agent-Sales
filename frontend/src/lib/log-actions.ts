"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { fetchApi } from "./api/client";
import { handleApiErrorToast } from "./api/error";
import type { components } from "./api/schema";

type VerifyOut = components["schemas"]["LogVerifyOut"];
type ExportOut = components["schemas"]["LogExportOut"];

export interface Soc2EvidenceItem {
  source?: string;
  type?: string;
  excerpt?: string;
  title?: string;
  note?: string;
  [key: string]: unknown;
}

export interface Soc2Receipt {
  receipt_id: string;
  entry_id: string | number;
  standard?: string;
  event: string;
  account_name?: string;
  account_id?: string;
  entity_id?: string;
  timestamp: string;
  summary?: string;
  org_id: string;
  actor_name?: string;
  actor_type?: string;
  actor_role?: string;
  autonomy_tier?: number;
  approval_status: string;
  entry_hash: string;
  prev_hash: string;
  chain_algorithm?: string;
  chain_status?: string;
  evidence_snapshot?: Soc2EvidenceItem[];
  tamper_verification_cli?: string;
  [key: string]: unknown;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Re-checks the decision log's hash chain on the server and reports what it actually found. */
export function useVerifyLog() {
  const [busy, setBusy] = useState(false);
  const verify = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetchApi<VerifyOut>("/log/verify");
      if (res.ok) {
        toast.success("Log integrity verified", {
          description: `${res.checked.toLocaleString()} entries checked. The hash chain is intact.`,
        });
      } else {
        toast.error("Log integrity check failed", {
          description: `The chain breaks at entry ${res.first_bad_id ?? "unknown"} after ${res.checked.toLocaleString()} entries checked.`,
          duration: 15000,
        });
      }
    } catch (err) {
      handleApiErrorToast(err);
    } finally {
      setBusy(false);
    }
  }, []);
  return { verify, busy };
}

/** Starts a log export job, waits for it, and downloads the file. */
export function useExportLog() {
  const [busy, setBusy] = useState(false);
  const exportLog = useCallback(async (format: "csv" | "json" = "csv") => {
    setBusy(true);
    try {
      let job = await fetchApi<ExportOut>("/log/export", { method: "POST", body: JSON.stringify({ format }) });
      for (let i = 0; i < 60 && job.status !== "done" && job.status !== "failed"; i++) {
        await sleep(1000);
        job = await fetchApi<ExportOut>(`/log/export/${job.job_id}`);
      }
      if (job.status === "failed") {
        toast.error("The export failed. Try again, or contact support if it keeps happening.");
        return;
      }
      if (job.status !== "done") {
        toast.error("The export is taking longer than expected. Try again in a minute.");
        return;
      }
      const res = await fetch(`/api/log/export/${job.job_id}/download`);
      if (!res.ok) {
        toast.error("Could not download the export.");
        return;
      }
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `decision-log.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Decision log exported");
    } catch (err) {
      handleApiErrorToast(err);
    } finally {
      setBusy(false);
    }
  }, []);
  return { exportLog, busy };
}
