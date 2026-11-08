import { describe, expect, it } from "vitest";

import { ago, day, rank, shortIdOf } from "./format";

describe("format", () => {
  it("makes a short id from the first four hex characters", () => {
    expect(shortIdOf("3f9a07e4-0000-4000-8000-000000000000")).toBe("3F9A");
  });

  it("shows priority as a two-digit rank", () => {
    expect([rank(0), rank(9)]).toEqual(["01", "10"]);
  });

  it("says how long ago, then falls back to a date", () => {
    const now = new Date(2026, 10, 8, 15, 0);
    const at = (d: Date) => ago(d.toISOString(), now);
    expect(at(new Date(2026, 10, 8, 14, 59, 30))).toBe("just now");
    expect(at(new Date(2026, 10, 8, 13, 0))).toBe("2h ago");
    expect(at(new Date(2026, 10, 7, 9, 0))).toBe("yesterday");
    expect(at(new Date(2026, 10, 5, 9, 0))).toBe("3d ago");
    expect(at(new Date(2026, 9, 2, 9, 0))).toBe("Oct 02");
  });

  it("writes log dates as month and two-digit day", () => {
    expect(day(new Date(2026, 10, 6, 12).toISOString())).toBe("Nov 06");
  });
});
