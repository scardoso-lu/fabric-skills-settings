import { kindBadgeClass, managedBadge, managedLabel } from "@/lib/utils";

describe("kindBadgeClass", () => {
  it("returns primary for skill", () => {
    expect(kindBadgeClass("skill")).toBe("badge-primary");
  });
  it("returns warning for rule", () => {
    expect(kindBadgeClass("rule")).toBe("badge-warning");
  });
  it("returns ghost for unknown kind", () => {
    expect(kindBadgeClass("unknown")).toBe("badge-ghost");
  });
});

describe("managedBadge", () => {
  it("success for managed", () => {
    expect(managedBadge(true)).toBe("badge-success");
  });
  it("warning for bundled", () => {
    expect(managedBadge(false)).toBe("badge-warning");
  });
});

describe("managedLabel", () => {
  it("managed label", () => {
    expect(managedLabel(true)).toBe("managed");
  });
  it("bundled label", () => {
    expect(managedLabel(false)).toBe("bundled");
  });
});
