"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { EmptyState } from "../../../../components/ui/empty-state";
import { ErrorState } from "../../../../components/ui/error-state";
import { DateText } from "../../../../components/ui/date-text";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { Key, Plus, Trash2, Copy, Check, AlertTriangle } from "lucide-react";

interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_at: string;
  last_used_at?: string | null;
}

interface ApiKeyCreated {
  id: string;
  name: string;
  prefix: string;
  key: string;
}

export default function ApiKeysSettingsPage() {
  const { can } = useMe();
  const queryClient = useQueryClient();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const {
    data: keys = [],
    isLoading,
    error,
    refetch,
  } = useQuery<ApiKeyItem[]>({
    queryKey: queryKeys.apiKeys(),
    queryFn: () => fetchApi<ApiKeyItem[]>("/api-keys"),
    enabled: can("apikeys:manage"),
  });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; scopes: string[] }) =>
      fetchApi<ApiKeyCreated>("/api-keys", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      setRevealedKey(data.key);
      setNewKeyName("");
      toast.success("API Key generated successfully");
      queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi(`/api-keys/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("API key revoked");
      queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const handleCopy = () => {
    if (revealedKey) {
      navigator.clipboard.writeText(revealedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.info("API Key copied to clipboard");
    }
  };

  return (
    <PermissionGuard action="apikeys:manage">
      {isLoading ? (
        <TableSkeleton rows={4} columns={4} />
      ) : error ? (
        <ErrorState
          title="Failed to load API keys"
          message={error instanceof Error ? error.message : "Unable to reach API"}
          onRetry={refetch}
        />
      ) : (
        <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              API Keys & Ingestion Tokens
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Manage authentication credentials for programmatic product usage pushing and custom integrations.
            </p>
          </div>
          <div>
            <button
              type="button"
              onClick={() => {
                setRevealedKey(null);
                setCreateModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500 active:bg-blue-700 transition-colors shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              Generate API Key
            </button>
          </div>
        </div>

        {keys.length === 0 ? (
          <EmptyState
            title="No API Keys Generated"
            description="Create an API key to stream product usage events or connect custom external pipelines."
            icon={<Key className="w-6 h-6" />}
          />
        ) : (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/20 text-slate-500 font-semibold">
                    <th className="py-3 px-5">Name & Prefix</th>
                    <th className="py-3 px-5">Scopes</th>
                    <th className="py-3 px-5">Created</th>
                    <th className="py-3 px-5">Last Used</th>
                    <th className="py-3 px-5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                  {keys.map((k) => (
                    <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <td className="py-3.5 px-5">
                        <div className="font-semibold text-slate-900 dark:text-slate-100">{k.name}</div>
                        <div className="text-[11px] font-mono text-slate-400 mt-0.5">{k.prefix}...</div>
                      </td>
                      <td className="py-3.5 px-5">
                        <div className="flex flex-wrap gap-1">
                          {k.scopes.map((s) => (
                            <span
                              key={s}
                              className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3.5 px-5">
                        <DateText date={k.created_at} />
                      </td>
                      <td className="py-3.5 px-5">
                        {k.last_used_at ? <DateText date={k.last_used_at} /> : "Never"}
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            if (confirm(`Revoke API key "${k.name}"? Any active integrations using this key will immediately fail.`)) {
                              revokeMutation.mutate(k.id);
                            }
                          }}
                          disabled={revokeMutation.isPending}
                          className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                          title="Revoke key"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Generate Key Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Key className="w-4 h-4 text-blue-500" />
                  Generate New API Key
                </h3>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 text-sm font-bold"
                >
                  ✕
                </button>
              </div>

              {revealedKey ? (
                <div className="space-y-4">
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <span>
                      Copy this secret key now. For security, this value is never stored in plaintext and will never be shown again.
                    </span>
                  </div>

                  <div className="flex items-center gap-2 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
                    <code className="text-xs font-mono text-slate-900 dark:text-slate-100 flex-1 break-all">
                      {revealedKey}
                    </code>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="p-1.5 rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 hover:bg-slate-50 text-slate-700 dark:text-slate-200"
                      title="Copy key"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="button"
                      onClick={() => setCreateModalOpen(false)}
                      className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500"
                    >
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!newKeyName.trim()) return;
                    createMutation.mutate({
                      name: newKeyName.trim(),
                      scopes: ["ingest:usage", "read:accounts"],
                    });
                  }}
                  className="space-y-4"
                >
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Key Identifier Name
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Production Data Warehouse Pipeline"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-3">
                    <button
                      type="button"
                      onClick={() => setCreateModalOpen(false)}
                      className="px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={createMutation.isPending || !newKeyName.trim()}
                      className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs"
                    >
                      {createMutation.isPending ? "Generating..." : "Generate Key"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
      )}
    </PermissionGuard>
  );
}
