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
import { ReadOnlyBanner } from "../../../../components/ui/read-only-banner";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import {
  Users,
  UserPlus,
  Crown,
  Shield,
  Trash2,
  Mail,
  CheckCircle,
  XCircle,
  AlertCircle,
} from "lucide-react";

interface Member {
  id: string;
  user_id: string;
  name?: string | null;
  email: string;
  role: "owner" | "admin" | "manager" | "member" | "viewer";
  status: "active" | "disabled";
  crm_owner_id?: string | null;
  slack_user_id?: string | null;
  integrations: string[];
}

interface Invite {
  id: string;
  email: string;
  role: "owner" | "admin" | "manager" | "member" | "viewer";
  expires_at: string;
}

export default function MembersSettingsPage() {
  const { me, activeRole, can } = useMe();
  const queryClient = useQueryClient();
  const canManageMembers = can("members:manage");
  const isOwner = can("ownership:transfer") || can("org:delete");

  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "manager" | "member" | "viewer">("member");

  // Fetch Members List
  const {
    data: membersData,
    isLoading: isMembersLoading,
    error: membersError,
    refetch: refetchMembers,
  } = useQuery<{ items: Member[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: Member[] }>("/members"),
    enabled: can("view:settings_members"),
  });

  // Fetch Invites List
  const { data: invitesData, refetch: refetchInvites } = useQuery<{ items: Invite[] }>({
    queryKey: ["invites"],
    queryFn: () => fetchApi<{ items: Invite[] }>("/invites"),
    enabled: canManageMembers,
  });

  const members = membersData?.items || [];
  const invites = invitesData?.items || [];

  // Invite Mutation
  const inviteMutation = useMutation({
    mutationFn: (body: { email: string; role: string }) =>
      fetchApi<Invite>("/invites", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (newInvite) => {
      toast.success("Invitation sent successfully", {
        description: `Invited ${newInvite.email} as ${newInvite.role}`,
      });
      setInviteModalOpen(false);
      setInviteEmail("");
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  // Role Change Mutation
  const updateRoleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      fetchApi<Member>(`/members/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    onSuccess: (updated) => {
      toast.success("Member role updated", {
        description: `${updated.email} is now ${updated.role}`,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.members() });
      queryClient.invalidateQueries({ queryKey: queryKeys.me() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  // Remove Member Mutation
  const removeMemberMutation = useMutation({
    mutationFn: (memberId: string) =>
      fetchApi(`/members/${memberId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("Member removed from workspace");
      queryClient.invalidateQueries({ queryKey: queryKeys.members() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  // Revoke Invite Mutation
  const revokeInviteMutation = useMutation({
    mutationFn: (inviteId: string) =>
      fetchApi(`/invites/${inviteId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("Invitation revoked");
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const handleInviteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;
    inviteMutation.mutate({
      email: inviteEmail.trim(),
      role: inviteRole,
    });
  };

  return (
    <PermissionGuard action="view:settings_members">
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Workspace Members & Access Control
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Manage seats, assign roles, configure CRM ownership mappings, and invite teammates.
            </p>
          </div>
          {canManageMembers && (
            <div>
              <button
                type="button"
                onClick={() => setInviteModalOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] active:bg-[#0A2018] transition-colors shadow-xs"
              >
                <UserPlus className="w-3.5 h-3.5" />
                Invite Teammate
              </button>
            </div>
          )}
        </div>

        {!canManageMembers && (
          <ReadOnlyBanner message="Only Owners and Admins can change this." />
        )}

        {/* Loading / Error States */}
        {isMembersLoading && <TableSkeleton rows={4} columns={5} />}

        {membersError && !isMembersLoading && (
          <ErrorState
            title="Failed to load workspace members"
            message={membersError instanceof Error ? membersError.message : "Unable to reach API"}
            onRetry={refetchMembers}
          />
        )}

        {/* Active Members Table */}
        {!isMembersLoading && !membersError && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs">
            <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Active Members ({members.length})
              </h2>
              {isOwner && (
                <span className="text-[11px] text-[#143C2E] dark:text-emerald-400 font-bold">
                  Owner Superpowers Active: Role Transfer & Management Enabled
                </span>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px] text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/20 text-slate-500 font-semibold">
                    <th className="py-3 px-5">Name & Email</th>
                    <th className="py-3 px-5">Role</th>
                    <th className="py-3 px-5">Status</th>
                    <th className="py-3 px-5">Connected Tools</th>
                    <th className="py-3 px-5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                  {members.map((m) => {
                    const isSelf = m.email === me?.user?.email;
                    return (
                      <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="py-3.5 px-5">
                          <div className="font-semibold text-slate-900 dark:text-slate-100">
                            {m.name || "—"}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono mt-0.5">{m.email}</div>
                        </td>

                        <td className="py-3.5 px-5">
                          {isOwner && !isSelf ? (
                            <select
                              value={m.role}
                              disabled={updateRoleMutation.isPending}
                              onChange={(e) =>
                                updateRoleMutation.mutate({
                                  memberId: m.id,
                                  role: e.target.value,
                                })
                              }
                              className="px-2.5 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-[#143C2E] capitalize font-medium"
                            >
                              <option value="owner">Owner</option>
                              <option value="admin">Admin</option>
                              <option value="manager">Manager</option>
                              <option value="member">Member</option>
                              <option value="viewer">Viewer</option>
                            </select>
                          ) : (
                            <div className="flex items-center gap-1.5 font-medium capitalize">
                              {m.role === "owner" && <Crown className="w-3.5 h-3.5 text-amber-500" />}
                              {m.role === "admin" && <Shield className="w-3.5 h-3.5 text-emerald-600" />}
                              <span>{m.role}</span>
                              {isSelf && (
                                <span className="text-[10px] text-slate-400 font-mono">(You)</span>
                              )}
                            </div>
                          )}
                        </td>

                        <td className="py-3.5 px-5">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                              m.status === "active"
                                ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border border-green-200 dark:border-green-800"
                                : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                            }`}
                          >
                            {m.status}
                          </span>
                        </td>

                        <td className="py-3.5 px-5">
                          <div className="flex flex-wrap gap-1">
                            {m.integrations.length === 0 ? (
                              <span className="text-slate-400 text-[11px]">—</span>
                            ) : (
                              m.integrations.map((int) => (
                                <span
                                  key={int}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono capitalize"
                                >
                                  {int}
                                </span>
                              ))
                            )}
                          </div>
                        </td>

                        <td className="py-3.5 px-5 text-right">
                          {canManageMembers && !isSelf && (m.role !== "owner" || isOwner) && (
                            <button
                              type="button"
                              onClick={() => {
                                if (
                                  confirm(
                                    `Are you sure you want to remove ${m.email} from the workspace?`
                                  )
                                ) {
                                  removeMemberMutation.mutate(m.id);
                                }
                              }}
                              disabled={removeMemberMutation.isPending}
                              className="text-red-500 hover:text-red-700 dark:text-red-400 p-1 rounded hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                              title="Remove member"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Pending Invites Section */}
        {invites.length > 0 && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs">
            <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Pending Invitations ({invites.length})
              </h2>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              {invites.map((inv) => (
                <div key={inv.id} className="p-4 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{inv.email}</span>
                    <span className="ml-2 px-2 py-0.5 text-[10px] font-mono rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 capitalize">
                      {inv.role}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => revokeInviteMutation.mutate(inv.id)}
                    disabled={revokeInviteMutation.isPending}
                    className="text-slate-500 hover:text-red-600 text-xs font-medium transition-colors"
                  >
                    Revoke
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Invite Member Modal */}
        {inviteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <UserPlus className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
                  Invite Teammate to Workspace
                </h3>
                <button
                  type="button"
                  onClick={() => setInviteModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 text-sm font-bold"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleInviteSubmit} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Work Email Address
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="colleague@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E]"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Assigned Workspace Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) =>
                      setInviteRole(e.target.value as "admin" | "manager" | "member" | "viewer")
                    }
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] capitalize"
                  >
                    <option value="admin">Admin — Full operational controls</option>
                    <option value="manager">Manager — Can review, edit rules & cards</option>
                    <option value="member">Member — Standard account analyst</option>
                    <option value="viewer">Viewer — Executive read-only</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setInviteModalOpen(false)}
                    className="px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={inviteMutation.isPending || !inviteEmail}
                    className="px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] active:bg-[#0A2018] disabled:opacity-50 transition-colors shadow-xs"
                  >
                    {inviteMutation.isPending ? "Sending invite..." : "Send Invitation"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
