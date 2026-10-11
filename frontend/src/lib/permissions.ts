/**
 * Client and Server permission checker.
 * Spec: spec.md §8, portals-and-impact.md §3.
 *
 * CRITICAL RULE: Built ONLY from permissions[] and flags{} (never from role string).
 */

export type AppAction =
  | "view:today"
  | "view:inbox"
  | "view:accounts"
  | "view:findings"
  | "view:log"
  | "view:outcomes"
  | "view:review"
  | "view:runs"
  | "view:team"
  | "view:control"
  | "view:analytics"
  | "view:rules"
  | "view:assistant"
  | "view:settings_profile"
  | "view:settings_connections"
  | "view:settings_notifications"
  | "view:settings_general"
  | "view:settings_members"
  | "view:settings_integrations"
  | "view:settings_field_mapping"
  | "view:settings_rules"
  | "view:settings_autonomy"
  | "view:settings_api_keys"
  | "view:settings_data"
  | "approve:card"
  | "reject:card"
  | "edit:card"
  | "revert:card"
  | "run:now"
  | "dismiss:finding"
  | "snooze:finding"
  | "edit:rules"
  | "rules:edit"
  | "manage:integrations"
  | "integrations:manage"
  | "manage:members"
  | "members:manage"
  | "manage:autonomy"
  | "autonomy:edit"
  | "manage:field_mapping"
  | "mapping:edit"
  | "field_mapping:edit"
  | "manage:api_keys"
  | "apikeys:manage"
  | "export:data"
  | "data:export"
  | "delete:org"
  | "org:delete"
  | "ownership:transfer"
  | "log:verify"
  | "log:export"
  | "members:manage_owner"
  | "role:manage_owner"
  | "role:assign_owner"
  | "assign:card"
  | "assign"
  | "model:view"
  | "view:model"
  | "run:retry"
  | "runs:retry";

export interface PermissionContext {
  isOwn?: boolean;
}

export function checkPermission(
  permissions: string[] = [],
  _flags: Record<string, boolean> = {},
  action: AppAction | string,
  context?: PermissionContext
): boolean {
  const permSet = new Set(permissions);

  switch (action) {
    // Navigation / View routes
    case "view:today":
    case "view:inbox":
    case "view:accounts":
    case "view:findings":
    case "view:log":
    case "view:outcomes":
      return permSet.has("view:accounts");

    case "view:review":
      return permSet.has("review:view");

    case "view:runs":
      return permSet.has("runs:view");

    case "view:team":
      return permSet.has("review:view") || permSet.has("runs:view");

    // The two customer portals (the API also reports them as `me.portals`)
    case "view:control":
    case "view:analytics":
      return permSet.has("analytics:view");

    case "view:rules":
    case "view:settings_rules":
      return permSet.has("rules:edit");

    // Riddhi, the workspace assistant: plain-language questions about the workspace's data
    case "view:assistant":
      return permSet.has("assistant:ask");

    // Personal settings (Work portal)
    case "view:settings_profile":
    case "view:settings_connections":
    case "view:settings_notifications":
      return permSet.has("connect:own") || permSet.has("view:accounts");

    // Workspace pages live in the Control portal: only people who can change them see them
    case "view:settings_integrations":
      return permSet.has("integrations:manage");

    case "view:settings_general":
    case "view:settings_members":
      return permSet.has("members:manage");

    case "view:settings_field_mapping":
      return permSet.has("mapping:edit");

    case "view:settings_autonomy":
      return permSet.has("autonomy:edit");

    case "view:settings_api_keys":
      return permSet.has("apikeys:manage");

    case "view:settings_data":
      return permSet.has("data:export") || permSet.has("org:delete");

    // Action execution (mutations)
    case "approve:card":
    case "reject:card":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("approve:own")) return true;
      return false;

    case "save:edits":
    case "edit:card":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("edit:card")) return true;
      return false;

    case "revert:card":
    case "revert":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("revert")) return true;
      return false;

    case "retry:card":
    case "retry":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("approve:own")) return true;
      return false;

    case "run:now":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("run:now")) return true;
      return false;

    case "dismiss:finding":
    case "snooze:finding":
    case "reopen:finding":
      return permSet.has("approve:any") || (Boolean(context?.isOwn) && permSet.has("approve:own"));

    case "edit:rules":
    case "rules:edit":
      return permSet.has("rules:edit");

    case "manage:integrations":
    case "integrations:manage":
      return permSet.has("integrations:manage");

    case "manage:members":
    case "members:manage":
      return permSet.has("members:manage");

    case "manage:autonomy":
    case "autonomy:edit":
      return permSet.has("autonomy:edit");

    case "manage:field_mapping":
    case "mapping:edit":
    case "field_mapping:edit":
      return permSet.has("mapping:edit");

    case "manage:api_keys":
    case "apikeys:manage":
      return permSet.has("apikeys:manage");

    case "export:data":
    case "data:export":
      return permSet.has("data:export");

    case "delete:org":
    case "org:delete":
      return permSet.has("org:delete");

    case "ownership:transfer":
      // Backend defines org:delete as # delete org, transfer ownership (Role.OWNER only)
      return permSet.has("org:delete");

    case "log:verify":
    case "log:export":
      return permSet.has("data:export");

    case "members:manage_owner":
    case "role:manage_owner":
    case "role:assign_owner":
      // Only Owner has org:delete; Admin cannot change, demote, remove or assign the Owner role
      return permSet.has("org:delete");

    case "assign:card":
    case "assign":
      // Manager+ (approve:any) can assign any card
      return permSet.has("approve:any");

    case "model:view":
    case "view:model":
      // Manager+ can inspect AI model info, latency, and prompt metadata
      return permSet.has("review:view") || permSet.has("rules:edit") || permSet.has("runs:view");

    case "run:retry":
    case "runs:retry":
      return permSet.has("runs:view");

    default:
      // Direct raw permission string fallback
      return permSet.has(action);
  }
}
