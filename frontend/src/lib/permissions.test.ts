import { describe, it, expect } from "vitest";
import { checkPermission } from "./permissions";

describe("Permissions Matrix (spec.md §8, portals-and-impact.md §3)", () => {
  // Backend permissions mapping per role from app/permissions.py
  const OWNER_PERMISSIONS = [
    "view:accounts",
    "connect:own",
    "approve:own",
    "edit:card",
    "revert",
    "run:now",
    "approve:any",
    "rules:edit",
    "review:view",
    "runs:view",
    "integrations:manage",
    "mapping:edit",
    "autonomy:edit",
    "members:manage",
    "apikeys:manage",
    "data:export",
    "analytics:view",
    "assistant:ask",
    "org:delete",
  ];

  const ADMIN_PERMISSIONS = OWNER_PERMISSIONS.filter((p) => p !== "org:delete");

  const MANAGER_PERMISSIONS = [
    "view:accounts",
    "connect:own",
    "approve:own",
    "edit:card",
    "revert",
    "run:now",
    "approve:any",
    "rules:edit",
    "review:view",
    "runs:view",
    "assistant:ask",
  ];

  const MEMBER_PERMISSIONS = [
    "view:accounts",
    "connect:own",
    "approve:own",
    "edit:card",
    "revert",
    "run:now",
  ];

  const VIEWER_PERMISSIONS = ["view:accounts", "connect:own"];

  describe("Riddhi (workspace assistant)", () => {
    it("is offered to Manager and above, never to Member or Viewer", () => {
      expect(checkPermission(OWNER_PERMISSIONS, {}, "view:assistant")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:assistant")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:assistant")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:assistant")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "view:assistant")).toBe(false);
    });
  });

  describe("Owner Role", () => {
    it("can perform everything including transfer ownership and delete workspace", () => {
      expect(checkPermission(OWNER_PERMISSIONS, {}, "ownership:transfer")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "delete:org")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "org:delete")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "members:manage")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "rules:edit")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "autonomy:edit")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "apikeys:manage")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "integrations:manage")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "data:export")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "mapping:edit")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "field_mapping:edit")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "approve:card")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "log:verify")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "log:export")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "members:manage_owner")).toBe(true);
      expect(checkPermission(OWNER_PERMISSIONS, {}, "role:assign_owner")).toBe(true);
    });
  });

  describe("Admin Role", () => {
    it("can manage people, rules, integrations, autonomy, log verify/export, but CANNOT delete org, transfer ownership, or manage owner role", () => {
      // 3 Denied Owner extras
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "ownership:transfer")).toBe(false);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "delete:org")).toBe(false);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "org:delete")).toBe(false);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "members:manage_owner")).toBe(false);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "role:assign_owner")).toBe(false);

      // Allowed Admin capabilities
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "members:manage")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "rules:edit")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "autonomy:edit")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "apikeys:manage")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "integrations:manage")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "data:export")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "log:verify")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "log:export")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "mapping:edit")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_data")).toBe(true);
      // Control portal: analytics plus every workspace page
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:control")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:analytics")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_general")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_members")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_integrations")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_field_mapping")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:settings_autonomy")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "approve:card")).toBe(true);
      expect(checkPermission(ADMIN_PERMISSIONS, {}, "view:accounts")).toBe(true);
    });
  });

  describe("Manager Role", () => {
    it("can approve/reject any card, edit/revert cards, run any account, tune rules, view team/reviews/runs/model info", () => {
      // Allowed operations across portal C
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:today")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:inbox")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:accounts")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:findings")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:log")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:outcomes")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:review")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:runs")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:team")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "approve:card")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "reject:card")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "edit:card")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "revert:card")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "run:now")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "assign:card")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "assign")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "model:view")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:model")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "run:retry")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "runs:retry")).toBe(true);

      // Allowed views in settings (read-only views)
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_profile")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_connections")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_notifications")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_rules")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "rules:edit")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "edit:rules")).toBe(true);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:rules")).toBe(true);
    });

    it("is strictly denied from configuring the workspace, managing members, exporting, or viewing D10/D11", () => {
      // The Control portal and every workspace page in it
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:control")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:analytics")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_general")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_members")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_integrations")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_field_mapping")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_autonomy")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_api_keys")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "view:settings_data")).toBe(false);

      // Denied mutations in settings
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "members:manage")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "manage:members")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "autonomy:edit")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "manage:autonomy")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "mapping:edit")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "manage:field_mapping")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "integrations:manage")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "manage:integrations")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "apikeys:manage")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "manage:api_keys")).toBe(false);

      // Denied export and verify integrity
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "data:export")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "export:data")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "log:verify")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "log:export")).toBe(false);

      // Denied Owner extras
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "org:delete")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "delete:org")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "ownership:transfer")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "members:manage_owner")).toBe(false);
      expect(checkPermission(MANAGER_PERMISSIONS, {}, "role:assign_owner")).toBe(false);
    });
  });

  describe("Member Role", () => {
    it("can only act on own accounts and own cards", () => {
      // Allowed on OWN
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "approve:card", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "reject:card", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "edit:card", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "save:edits", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "revert:card", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "revert", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "retry:card", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "retry", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "run:now", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "dismiss:finding", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "snooze:finding", { isOwn: true })).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "reopen:finding", { isOwn: true })).toBe(true);

      // Denied on NOT OWN
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "approve:card", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "reject:card", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "edit:card", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "revert:card", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "retry:card", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "run:now", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "dismiss:finding", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "snooze:finding", { isOwn: false })).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "reopen:finding", { isOwn: false })).toBe(false);
    });

    it("confirms exclusion of team/admin tooling, rules edit, review, runs, model info, assign, settings", () => {
      // Excluded routes & features
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "review:view")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:review")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "runs:view")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:runs")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "team:view")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:team")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "model:view")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:model")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "rules:edit")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "edit:rules")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_rules")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "approve:any")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "assign:card")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "assign")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "members:manage")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "integrations:manage")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "mapping:edit")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "autonomy:edit")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "apikeys:manage")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "data:export")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "log:verify")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "log:export")).toBe(false);

      // Excluded settings views
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_general")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_members")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_field_mapping")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_autonomy")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_api_keys")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_data")).toBe(false);

      // Allowed views in portal C and D
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:today")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:inbox")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:accounts")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:findings")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:log")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:outcomes")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_profile")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_connections")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_notifications")).toBe(true);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:settings_integrations")).toBe(false);
      expect(checkPermission(MEMBER_PERMISSIONS, {}, "view:control")).toBe(false);
    });
  });

  describe("Viewer Role", () => {
    it("is strictly read-only and denied on all mutation actions", () => {
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "view:today")).toBe(true);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "view:accounts")).toBe(true);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "approve:card")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "edit:card")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "reject:card")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "members:manage")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "ownership:transfer")).toBe(false);
      expect(checkPermission(VIEWER_PERMISSIONS, {}, "delete:org")).toBe(false);
    });
  });

  describe("Ownership Resolution (checkEntityOwnership)", () => {
    it("correctly identifies ownership for accounts and cards by owner/assignee id", async () => {
      const { checkEntityOwnership } = await import("./auth/use-is-mine");

      // Account with owner_user_id
      expect(checkEntityOwnership({ owner_user_id: "user-123" }, "user-123").isMine).toBe(true);
      expect(checkEntityOwnership({ owner_user_id: "user-123" }, "user-456").isMine).toBe(false);

      // Account with owner.id
      expect(
        checkEntityOwnership({ owner: { id: "user-123", name: "Alice" } }, "user-123").isMine
      ).toBe(true);
      expect(
        checkEntityOwnership({ owner: { id: "user-123", name: "Alice" } }, "user-456").isMine
      ).toBe(false);

      // Card with assignee_user_id / assignee_id
      expect(checkEntityOwnership({ assignee_user_id: "user-123" }, "user-123").isMine).toBe(true);
      expect(checkEntityOwnership({ assignee_id: "user-123" }, "user-123").isMine).toBe(true);
      expect(checkEntityOwnership({ assignee_user_id: "user-123" }, "user-456").isMine).toBe(false);

      // Ownership comes only from owner/assignee ids, never from account names
      expect(
        checkEntityOwnership({ owner_name: "Priya Sharma" }, "user-123", "member").isMine
      ).toBe(false);
      expect(checkEntityOwnership({}, "user-123").isMine).toBe(false);
      expect(checkEntityOwnership({ owner_user_id: "user-123" }, undefined).isMine).toBe(false);
    });
  });
});
