import { clearExpiresAt, getExpiresAt, isAuthenticated, isTokenExpired, setExpiresAt } from "@/lib/auth";

describe("auth expiry helpers (cookie-based, no token in JS)", () => {
  beforeEach(() => {
    // Reset the expiry cookie before each test.
    document.cookie = "fab_expires_at=; path=/; max-age=0";
  });

  it("returns null when no expiry cookie is set", () => {
    expect(getExpiresAt()).toBeNull();
  });

  it("stores and retrieves expiry hint", () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    setExpiresAt(future);
    expect(getExpiresAt()).toBe(future);
  });

  it("reports not expired for a future expiry", () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    setExpiresAt(future);
    expect(isTokenExpired()).toBe(false);
  });

  it("reports expired for a past expiry", () => {
    const past = new Date(Date.now() - 1000).toISOString();
    setExpiresAt(past);
    expect(isTokenExpired()).toBe(true);
  });

  it("isAuthenticated returns false when no expiry cookie", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("isAuthenticated returns true with valid future expiry", () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    setExpiresAt(future);
    expect(isAuthenticated()).toBe(true);
  });

  it("clears expiry hint", () => {
    setExpiresAt(new Date(Date.now() + 3600_000).toISOString());
    clearExpiresAt();
    expect(getExpiresAt()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});
