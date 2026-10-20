import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_PREFERENCES, normalizePreferences, resolveTheme, stepFontSize, stepLineHeight } from "./preferences.ts";

test("missing or broken stored preferences fall back to defaults", () => {
  assert.deepEqual(normalizePreferences(null), DEFAULT_PREFERENCES);
  assert.deepEqual(normalizePreferences("nonsense"), DEFAULT_PREFERENCES);
  assert.deepEqual(normalizePreferences({ mode: "klingon", theme: 3, fontSize: "big" }), DEFAULT_PREFERENCES);
});

test("bilingual is the default display mode", () => {
  assert.equal(DEFAULT_PREFERENCES.mode, "both");
  assert.equal(DEFAULT_PREFERENCES.typeface, "sans");
});

test("font size and line height stay within their ranges", () => {
  assert.equal(normalizePreferences({ fontSize: 99 }).fontSize, 24);
  assert.equal(normalizePreferences({ fontSize: 2 }).fontSize, 14);
  assert.equal(normalizePreferences({ lineHeight: 5 }).lineHeight, 2.1);
  assert.equal(stepFontSize(24, 1), 24);
  assert.equal(stepFontSize(14, -1), 14);
  assert.equal(stepFontSize(18, 1), 19);
});

test("line-height steps do not drift", () => {
  let value = 1.4;
  for (let i = 0; i < 3; i += 1) value = stepLineHeight(value, 1);
  assert.equal(value, 1.7);
  assert.equal(stepLineHeight(2.1, 1), 2.1);
});

test("valid choices are kept", () => {
  const prefs = normalizePreferences({ mode: "secondary", theme: "sepia", fontSize: 20, lineHeight: 1.9, typeface: "serif" });
  assert.deepEqual(prefs, { mode: "secondary", theme: "sepia", fontSize: 20, lineHeight: 1.9, typeface: "serif" });
});

test("the system theme follows the device", () => {
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");
  assert.equal(resolveTheme("sepia", true), "sepia");
});
