"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Plus, Trash2, XCircle } from "lucide-react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { fetchApi } from "../../../../lib/api/client";
import { ApiError } from "../../../../lib/api/error";
import { useMe } from "../../../../lib/auth/session-context";
import { nextPath } from "../../../../lib/onboarding/steps";

interface Row {
  email: string;
  role: string;
  state: "idle" | "sent" | "failed";
  message?: string;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const fieldClass =
  "px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500";

export default function OnboardingInvitePage() {
  const router = useRouter();
  const { me } = useMe();
  // The API says which roles this user may grant; the UI never works that out itself.
  const roles = me?.invitable_roles ?? [];
  const defaultRole = roles.includes("member") ? "member" : (roles[0] ?? "");
  const [rows, setRows] = useState<Row[]>([{ email: "", role: defaultRole, state: "idle" }]);
  const [busy, setBusy] = useState(false);

  const update = (i: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const filled = rows.filter((r) => r.email.trim() !== "" && r.state !== "sent");
  const invalid = filled.some((r) => !EMAIL.test(r.email.trim()) || !r.role);

  const send = async () => {
    setBusy(true);
    let failures = 0;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (r.email.trim() === "" || r.state === "sent") continue;
      try {
        await fetchApi("/invites", {
          method: "POST",
          body: JSON.stringify({ email: r.email.trim(), role: r.role }),
        });
        update(i, { state: "sent", message: undefined });
      } catch (err) {
        failures++;
        update(i, { state: "failed", message: err instanceof ApiError ? err.message : "Could not send" });
      }
    }
    setBusy(false);
    if (failures === 0) router.push(nextPath("invite", true));
  };

  return (
    <PermissionGuard action="members:manage">
      <OnboardingShell
        step="invite"
        title="Invite your team"
        description="Teammates get an email with a link that is valid for 7 days. They choose their own password and connect their own Google account."
        allowSkip
        onContinue={send}
        busy={busy}
        canContinue={filled.length > 0 && !invalid && roles.length > 0}
        continueLabel={
          filled.length > 0 ? `Send ${filled.length} invite${filled.length === 1 ? "" : "s"}` : "Add an email to invite"
        }
      >
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center gap-2">
                <input
                  type="email"
                  aria-label={`Email ${i + 1}`}
                  value={r.email}
                  disabled={r.state === "sent"}
                  onChange={(e) => update(i, { email: e.target.value, state: "idle" })}
                  placeholder="name@company.com"
                  className={`${fieldClass} flex-1 min-w-0`}
                />
                <select
                  aria-label={`Role ${i + 1}`}
                  value={r.role}
                  disabled={r.state === "sent"}
                  onChange={(e) => update(i, { role: e.target.value })}
                  className={`${fieldClass} capitalize`}
                >
                  {roles.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
                {r.state === "sent" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" aria-label="Sent" />
                ) : r.state === "failed" ? (
                  <XCircle className="w-4 h-4 text-rose-600" aria-label="Failed" />
                ) : (
                  <button
                    type="button"
                    aria-label={`Remove row ${i + 1}`}
                    disabled={rows.length === 1}
                    onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                    className="text-slate-400 hover:text-slate-600 disabled:opacity-30 cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
              {r.state === "failed" && <p className="text-[11px] text-rose-600">{r.message}</p>}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, { email: "", role: defaultRole, state: "idle" }])}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-800 dark:text-lime-400 cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" /> Add another
        </button>
      </OnboardingShell>
    </PermissionGuard>
  );
}
