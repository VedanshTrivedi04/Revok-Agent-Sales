import { toast } from "sonner";

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function parseApiError(status: number, body: unknown): ApiError {
  if (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as ErrorEnvelope).error === "object"
  ) {
    const envelope = body as ErrorEnvelope;
    return new ApiError(
      status,
      envelope.error.code || "unknown_error",
      envelope.error.message || "An unexpected error occurred",
      envelope.error.details
    );
  }

  return new ApiError(status, `http_${status}`, `Request failed with status ${status}`);
}

export type KnownErrorCode =
  | "last_owner"
  | "last_owner_required"
  | "cannot_change_owner"
  | "card_not_pending"
  | "stale_preview"
  | "recipient_not_allowed"
  | "tier_blocked"
  | "revert_conflict"
  | "integration_needs_reauth"
  | "validation_error"
  | "rate_limited"
  | "org_suspended"
  | "forbidden"
  | "conflict"
  | "not_found";

export function handleApiErrorToast(error: unknown) {
  if (!(error instanceof ApiError)) {
    toast.error(error instanceof Error ? error.message : "An unexpected error occurred");
    return;
  }

  switch (error.code) {
    case "last_owner":
    case "last_owner_required":
      toast.error("Cannot modify last Owner: A workspace must always have at least one active Owner.");
      break;
    case "cannot_change_owner":
      toast.error("Permission denied: Only an active Owner can modify an Owner's role or transfer ownership.");
      break;
    case "card_not_pending":
      toast.warning("Already decided: This card was already processed or is no longer pending.");
      break;
    case "stale_preview":
      toast.error("CRM value changed: The data changed in HubSpot since the preview was created. Please refresh the proposal.");
      break;
    case "recipient_not_allowed":
      toast.error("Recipient blocked: Email recipient is not in the account contact allowlist.");
      break;
    case "revert_conflict":
      toast.error("Revert conflict: Newer CRM edits exist. Reverting now would overwrite newer data.");
      break;
    case "tier_blocked":
      toast.error("Action blocked: Tier 3 actions cannot be executed directly by policy.");
      break;
    case "integration_needs_reauth":
      toast.error("Connection expired: Please reconnect your integration in Settings.");
      break;
    case "validation_error":
      toast.error(`Validation error: ${error.message || "Please check the entered values."}`);
      break;
    case "rate_limited":
      toast.warning("Too many requests: Please slow down and try again shortly.");
      break;
    case "org_suspended":
      toast.error("Workspace suspended: Contact support to restore access.");
      break;
    case "forbidden":
      toast.error("Access denied: You do not have permission for this action.");
      break;
    default:
      toast.error(error.message);
      break;
  }
}
