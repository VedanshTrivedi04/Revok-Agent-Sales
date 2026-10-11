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
  | "manage:integrations"
  | "manage:members"
  | "manage:autonomy"
  | "manage:field_mapping"
  | "manage:api_keys"
  | "export:data"
  | "delete:org";

export interface PermissionContext {
  isOwn?: boolean;
}

export function checkPermission(
  permissions: string[] = [],
  flags: Record<string, boolean> = {},
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

    // Settings sub-pages
    case "view:settings_profile":
    case "view:settings_connections":
    case "view:settings_notifications":
      return permSet.has("connect:own") || permSet.has("view:accounts");

    case "view:settings_integrations":
      return permSet.has("view:accounts");

    case "view:settings_general":
    case "view:settings_members":
      return permSet.has("members:manage");

    case "view:settings_field_mapping":
      return permSet.has("mapping:edit");

    case "view:settings_rules":
      return permSet.has("rules:edit");

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

    case "edit:card":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("edit:card")) return true;
      return false;

    case "revert:card":
      if (permSet.has("approve:any") || permSet.has("revert")) return true;
      return false;

    case "run:now":
      if (permSet.has("approve:any")) return true;
      if (context?.isOwn && permSet.has("run:now")) return true;
      return false;

    case "dismiss:finding":
    case "snooze:finding":
      return permSet.has("approve:any") || (Boolean(context?.isOwn) && permSet.has("approve:own"));

    case "edit:rules":
      return permSet.has("rules:edit");

    case "manage:integrations":
      return permSet.has("integrations:manage");

    case "manage:members":
      return permSet.has("members:manage");

    case "manage:autonomy":
      return permSet.has("autonomy:edit");

    case "manage:field_mapping":
      return permSet.has("mapping:edit");

    case "manage:api_keys":
      return permSet.has("apikeys:manage");

    case "export:data":
      return permSet.has("data:export");

    case "delete:org":
      return permSet.has("org:delete");

    default:
      // Direct raw permission string fallback
      return permSet.has(action);
  }
}
