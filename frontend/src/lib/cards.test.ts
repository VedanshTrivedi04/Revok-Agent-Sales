import { describe, expect, it } from "vitest";
import { activePayload, buildEditedPayload, hasPricingLanguage, isStalePreview, recipients } from "./cards";

const email = {
  type: "email_draft" as const,
  payload: { to: ["a@x.com"], subject: "Checking in", body_text: "Hi", mode: "draft" },
  edited_payload: null,
};

describe("card helpers", () => {
  it("detects a stale CRM preview from the executor error", () => {
    expect(isStalePreview("stale_preview: lifecycle changed")).toBe(true);
    expect(isStalePreview("HubSpot 500")).toBe(false);
    expect(isStalePreview(null)).toBe(false);
  });

  it("flags pricing language as a hint", () => {
    expect(hasPricingLanguage("We can offer a 20% off renewal")).toBe(true);
    expect(hasPricingLanguage("Quick question about the rollout")).toBe(false);
    expect(hasPricingLanguage(null, undefined, "pricing review")).toBe(true);
  });

  it("builds an edited payload only when something really changed", () => {
    expect(buildEditedPayload(email, { subject: "Checking in", body_text: "Hi" })).toBeNull();
    expect(buildEditedPayload(email, { subject: "New subject", body_text: "Hi" })).toEqual({
      ...email.payload,
      subject: "New subject",
    });
  });

  it("never lets recipients or other protected fields be edited", () => {
    const edited = buildEditedPayload(email, { subject: "x", to: "evil@x.com" });
    expect(edited?.to).toEqual(["a@x.com"]);
  });

  it("layers edits over the proposal", () => {
    expect(activePayload({ payload: { a: 1, b: 2 }, edited_payload: { b: 3 } })).toEqual({ a: 1, b: 3 });
    expect(recipients({ to: ["a@x.com", 5] }, "to")).toEqual(["a@x.com"]);
    expect(recipients({}, "cc")).toEqual([]);
  });
});
