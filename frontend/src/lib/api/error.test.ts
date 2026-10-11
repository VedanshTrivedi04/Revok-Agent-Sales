import { describe, it, expect, vi } from "vitest";
import { parseApiError, handleApiErrorToast, ApiError } from "./error";
import { generateIdempotencyKey } from "./client";
import { toast } from "sonner";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}));

describe("API Error & Idempotency", () => {
  it("parses structured error envelope from backend correctly", () => {
    const errorBody = {
      error: {
        code: "last_owner_required",
        message: "Cannot demote or disable the last active owner",
        details: { active_owners: 1 },
      },
    };

    const err = parseApiError(400, errorBody);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("last_owner_required");
    expect(err.message).toBe("Cannot demote or disable the last active owner");
    expect(err.details).toEqual({ active_owners: 1 });
    expect(err.status).toBe(400);
  });

  it("handles fallback error parsing for unstructured response", () => {
    const err = parseApiError(500, "Internal Server Error");
    expect(err.code).toBe("http_500");
    expect(err.status).toBe(500);
  });

  it("triggers specific friendly toast messages for known error codes", () => {
    handleApiErrorToast(new ApiError(400, "last_owner_required", "Cannot modify last owner"));
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Cannot modify last Owner")
    );

    handleApiErrorToast(new ApiError(403, "cannot_change_owner", "Forbidden"));
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Only an active Owner can modify an Owner's role")
    );

    handleApiErrorToast(new ApiError(409, "card_not_pending", "Card decided"));
    expect(toast.warning).toHaveBeenCalledWith(
      expect.stringContaining("Already decided")
    );

    handleApiErrorToast(new ApiError(409, "stale_preview", "Stale"));
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("CRM value changed")
    );

    handleApiErrorToast(new ApiError(400, "recipient_not_allowed", "Not allowed"));
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Recipient blocked")
    );
  });

  it("generates unique idempotency keys", () => {
    const key1 = generateIdempotencyKey();
    const key2 = generateIdempotencyKey();
    expect(key1).toBeTruthy();
    expect(key2).toBeTruthy();
    expect(key1).not.toBe(key2);
  });
});
