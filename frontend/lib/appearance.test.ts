import assert from "node:assert/strict";
import { test } from "node:test";

import { APPEARANCE_BOOT_SCRIPT, APPEARANCE_KEY, DEFAULT_APPEARANCE, normalizeAppearance, resolveAppearance } from "./appearance.ts";

test("only the three known modes are accepted", () => {
  for (const mode of ["light", "dark", "system"]) assert.equal(normalizeAppearance(mode), mode);
  for (const bad of [undefined, null, "", "Dark", "sepia", 1, {}, "system "]) assert.equal(normalizeAppearance(bad), DEFAULT_APPEARANCE);
});

test("system follows the device, light and dark do not", () => {
  assert.equal(resolveAppearance("system", true), "dark");
  assert.equal(resolveAppearance("system", false), "light");
  assert.equal(resolveAppearance("dark", false), "dark");
  assert.equal(resolveAppearance("light", true), "light");
});

// Run the boot script against a minimal stand-in for the browser to check what it sets before first paint.
function boot(stored: string | null, prefersDark: boolean, storageThrows = false) {
  const attrs: Record<string, string> = {};
  const html = { setAttribute: (name: string, value: string) => { attrs[name] = value; }, style: {} as Record<string, string> };
  const localStorage = { getItem: (key: string) => { if (storageThrows) throw new Error("blocked"); return key === APPEARANCE_KEY ? stored : null; } };
  const window = { matchMedia: () => ({ matches: prefersDark }) };
  new Function("localStorage", "document", "window", "matchMedia", APPEARANCE_BOOT_SCRIPT)(
    localStorage, { documentElement: html }, window, window.matchMedia);
  return { theme: attrs["data-app-theme"], scheme: html.style.colorScheme };
}

test("the boot script applies the saved mode before paint", () => {
  assert.deepEqual(boot("dark", false), { theme: "dark", scheme: "dark" });
  assert.deepEqual(boot("light", true), { theme: "light", scheme: "light" });
  assert.deepEqual(boot("system", true), { theme: "dark", scheme: "dark" });
  assert.deepEqual(boot("system", false), { theme: "light", scheme: "light" });
});

test("the boot script falls back to light for nothing, junk, or blocked storage", () => {
  for (const stored of [null, "", "sepia", "DARK"]) assert.equal(boot(stored, true).theme, "light", String(stored));
  assert.equal(boot(null, true, true).theme, "light");
});
