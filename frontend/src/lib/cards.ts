import type { components } from "./api/schema";

export type CardOut = components["schemas"]["CardOut"];
export type CardType = CardOut["type"];

export const CARD_TYPE_LABEL: Record<CardType, string> = {
  email_draft: "Email draft",
  crm_task: "HubSpot task",
  crm_field_update: "HubSpot field update",
  crm_note: "HubSpot note",
  slack_internal: "Slack message",
  meeting_request: "Meeting request",
};

/** Reject reasons accepted by the API (`CardRejectIn.reason`). */
export const REJECT_REASONS: Array<{ value: "wrong_action" | "wrong_content" | "not_now" | "already_done" | "other"; label: string }> = [
  { value: "wrong_action", label: "Wrong action" },
  { value: "wrong_content", label: "Wrong content" },
  { value: "not_now", label: "Not now" },
  { value: "already_done", label: "Already done" },
  { value: "other", label: "Other" },
];

/** The CRM value changed between the preview and the write, so the executor stopped. */
export function isStalePreview(error: string | null | undefined): boolean {
  return typeof error === "string" && error.toLowerCase().includes("stale");
}

const PRICING = /(\bdiscount|\bprice\b|\bpricing\b|\d+\s?%\s?off|\brefund|\bfree (month|trial)|\bcoupon)/i;

/** A hint only; the backend policy is the real guard (frontenddeveloper.md C4). */
export function hasPricingLanguage(...texts: Array<string | null | undefined>): boolean {
  return texts.some((t) => typeof t === "string" && PRICING.test(t));
}

const str = (v: unknown): string => (typeof v === "string" ? v : "");

/**
 * What the card will actually execute: the person's edits when there are any, else the proposal.
 * Edits are stored as a whole replacement payload, so unedited fields stay as proposed.
 */
export function activePayload(card: Pick<CardOut, "payload" | "edited_payload">): Record<string, unknown> {
  return { ...card.payload, ...(card.edited_payload ?? {}) };
}

/** Fields a person may change per card type, and where each lives in the payload. */
export const EDITABLE_FIELDS: Record<CardType, string[]> = {
  email_draft: ["subject", "body_text"],
  crm_task: ["title", "body", "due_date", "priority"],
  crm_field_update: [],
  crm_note: ["body"],
  slack_internal: ["text"],
  meeting_request: [],
};

/** Builds the edited payload from form values, or null when nothing differs from the proposal. */
export function buildEditedPayload(
  card: Pick<CardOut, "type" | "payload" | "edited_payload">,
  values: Record<string, string>
): Record<string, unknown> | null {
  const base = activePayload(card);
  const next: Record<string, unknown> = { ...base };
  let changed = false;
  for (const key of EDITABLE_FIELDS[card.type]) {
    if (key in values && values[key] !== str(base[key])) {
      next[key] = values[key];
      changed = true;
    }
  }
  return changed ? next : null;
}

export function recipients(payload: Record<string, unknown>, key: "to" | "cc"): string[] {
  const v = payload[key];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}
