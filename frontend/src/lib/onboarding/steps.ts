/**
 * Onboarding journey (portals-and-impact.md §5.2). Owners and Admins walk the whole list; everyone
 * else only sees the steps marked `everyone`. Which flow a user gets is decided by permissions
 * (`integrations:manage`), never by a role string.
 */
export type StepKey =
  | "org"
  | "hubspot"
  | "mapping"
  | "usage"
  | "slack"
  | "invite"
  | "google"
  | "first-sync";

export interface OnboardingStep {
  key: StepKey;
  path: string;
  label: string;
  /** Visible to users without `integrations:manage` too. */
  everyone: boolean;
  /** Matching key in `GET /me` → `onboarding.steps`, when the API tracks this step. */
  apiKey?: string;
  /** The user may continue without completing it. */
  optional: boolean;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  { key: "org", path: "/onboarding/org", label: "Workspace", everyone: false, apiKey: "org", optional: false },
  { key: "hubspot", path: "/onboarding/hubspot", label: "HubSpot", everyone: false, apiKey: "hubspot", optional: false },
  { key: "mapping", path: "/onboarding/field-mapping", label: "Field mapping", everyone: false, apiKey: "mapping", optional: false },
  { key: "usage", path: "/onboarding/usage", label: "Usage data", everyone: false, apiKey: "usage", optional: true },
  { key: "slack", path: "/onboarding/slack", label: "Slack", everyone: true, apiKey: "slack", optional: true },
  { key: "invite", path: "/onboarding/invite", label: "Invite team", everyone: false, apiKey: "invite", optional: true },
  { key: "google", path: "/onboarding/google", label: "Google", everyone: true, optional: true },
  { key: "first-sync", path: "/onboarding/first-sync", label: "First insights", everyone: true, optional: false },
];

export function visibleSteps(isAdminFlow: boolean): OnboardingStep[] {
  return ONBOARDING_STEPS.filter((s) => isAdminFlow || s.everyone);
}

/** The step after `key` in this user's flow, or `/today` when it was the last one. */
export function nextPath(key: StepKey, isAdminFlow: boolean): string {
  const steps = visibleSteps(isAdminFlow);
  const i = steps.findIndex((s) => s.key === key);
  return i >= 0 && i < steps.length - 1 ? steps[i + 1].path : "/today";
}

/** Human messages for `?error=` codes the OAuth callback can return. */
export function oauthErrorMessage(code: string): string {
  switch (code) {
    case "access_denied":
      return "Access was denied at the provider. Try connecting again and approve the requested permissions.";
    case "invalid_state":
      return "That sign-in link expired or was already used. Start the connection again.";
    case "exchange_failed":
      return "The provider did not accept the connection. Try again in a moment.";
    case "unsupported_provider":
      return "This provider cannot be connected yet.";
    default:
      return `The connection failed (${code}). Try again, or contact support if it keeps happening.`;
  }
}
