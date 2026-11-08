import { describe, expect, it } from "vitest";

import { readPref, resolve, setPref } from "./theme";

describe("theme", () => {
  it("is dark unless set otherwise, whatever the phone prefers", () => {
    localStorage.clear();
    expect(readPref()).toBe("dark");
    expect(resolve("dark", true)).toBe("dark");
  });

  it("follows the phone only when asked to", () => {
    expect(resolve("system", true)).toBe("light");
    expect(resolve("system", false)).toBe("dark");
  });

  it("saves the setting and applies it to the page", () => {
    setPref("light");
    expect(readPref()).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    setPref("dark");
  });
});
