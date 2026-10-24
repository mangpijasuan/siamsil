import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_DIRECTION,
  languages,
  orientPair,
  parseDirection,
  reverseDirection,
  swapState,
  translateHref,
} from "./translate.ts";

// Placeholder text stands in for Zomi; tests never invent Zomi language data.
const pair = { english: "water", zomi: "ZOMI_PLACEHOLDER" };

test("links without a direction read as English to Zomi (older links keep working)", () => {
  assert.equal(DEFAULT_DIRECTION, "en-zom");
  assert.equal(parseDirection(undefined), "en-zom");
  assert.equal(parseDirection(null), "en-zom");
  assert.equal(parseDirection(""), "en-zom");
});

test("unknown directions fall back to the default instead of failing", () => {
  assert.equal(parseDirection("fr-zom"), "en-zom");
  assert.equal(parseDirection(["zom-en", "en-zom"]), "zom-en");
});

test("both directions parse", () => {
  assert.equal(parseDirection("en-zom"), "en-zom");
  assert.equal(parseDirection("zom-en"), "zom-en");
});

test("reversing twice returns the original direction", () => {
  assert.equal(reverseDirection("en-zom"), "zom-en");
  assert.equal(reverseDirection(reverseDirection("en-zom")), "en-zom");
});

test("source and target languages follow the direction", () => {
  assert.deepEqual(
    [languages("en-zom").source.name, languages("en-zom").target.name],
    ["English", "Zomi"],
  );
  assert.deepEqual(
    [languages("zom-en").source.name, languages("zom-en").target.name],
    ["Zomi", "English"],
  );
});

test("a stored pair is shown source first, target second, in either direction", () => {
  assert.deepEqual(orientPair(pair, "en-zom"), { source: "water", target: "ZOMI_PLACEHOLDER" });
  assert.deepEqual(orientPair(pair, "zom-en"), { source: "ZOMI_PLACEHOLDER", target: "water" });
});

test("lookup links always carry the direction and encode the text", () => {
  assert.equal(translateHref("good morning", "en-zom"), "/zomitranslate?q=good+morning&dir=en-zom");
  assert.equal(translateHref("  a&b ", "zom-en"), "/zomitranslate?q=a%26b&dir=zom-en");
  assert.equal(translateHref("   ", "zom-en"), "/zomitranslate?dir=zom-en");
});

test("swapping with a translation shown moves it into the input", () => {
  assert.deepEqual(swapState("water", "en-zom", "ZOMI_PLACEHOLDER"), {
    text: "ZOMI_PLACEHOLDER",
    direction: "zom-en",
  });
});

test("swapping without a translation keeps the typed text", () => {
  assert.deepEqual(swapState("water", "en-zom", null), { text: "water", direction: "zom-en" });
  assert.deepEqual(swapState("water", "zom-en", "   "), { text: "water", direction: "en-zom" });
});

test("swapping twice returns to the starting direction", () => {
  const once = swapState("water", "en-zom", "ZOMI_PLACEHOLDER");
  const twice = swapState(once.text, once.direction, "water");
  assert.deepEqual(twice, { text: "water", direction: "en-zom" });
});
