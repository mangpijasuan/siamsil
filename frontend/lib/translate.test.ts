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
  assert.equal(DEFAULT_DIRECTION, "en-ctd");
  assert.equal(parseDirection(undefined), "en-ctd");
  assert.equal(parseDirection(null), "en-ctd");
  assert.equal(parseDirection(""), "en-ctd");
});

test("unknown directions fall back to the default instead of failing", () => {
  assert.equal(parseDirection("fr-zom"), "en-ctd");
  assert.equal(parseDirection(["ctd-en", "en-ctd"]), "ctd-en");
});

test("both directions parse", () => {
  assert.equal(parseDirection("en-ctd"), "en-ctd");
  assert.equal(parseDirection("ctd-en"), "ctd-en");
});

test("links from before Zomi was labelled ctd still open the same direction", () => {
  assert.equal(parseDirection("zom-en"), "ctd-en");
  assert.equal(parseDirection("en-zom"), "en-ctd");
});

test("reversing twice returns the original direction", () => {
  assert.equal(reverseDirection("en-ctd"), "ctd-en");
  assert.equal(reverseDirection(reverseDirection("en-ctd")), "en-ctd");
});

test("source and target languages follow the direction", () => {
  assert.deepEqual(
    [languages("en-ctd").source.name, languages("en-ctd").target.name],
    ["English", "Zomi"],
  );
  assert.deepEqual(
    [languages("ctd-en").source.name, languages("ctd-en").target.name],
    ["Zomi", "English"],
  );
});

test("a stored pair is shown source first, target second, in either direction", () => {
  assert.deepEqual(orientPair(pair, "en-ctd"), { source: "water", target: "ZOMI_PLACEHOLDER" });
  assert.deepEqual(orientPair(pair, "ctd-en"), { source: "ZOMI_PLACEHOLDER", target: "water" });
});

test("lookup links always carry the direction and encode the text", () => {
  assert.equal(translateHref("good morning", "en-ctd"), "/zomitranslate?q=good+morning&dir=en-ctd");
  assert.equal(translateHref("  a&b ", "ctd-en"), "/zomitranslate?q=a%26b&dir=ctd-en");
  assert.equal(translateHref("   ", "ctd-en"), "/zomitranslate?dir=ctd-en");
});

test("swapping with a translation shown moves it into the input", () => {
  assert.deepEqual(swapState("water", "en-ctd", "ZOMI_PLACEHOLDER"), {
    text: "ZOMI_PLACEHOLDER",
    direction: "ctd-en",
  });
});

test("swapping without a translation keeps the typed text", () => {
  assert.deepEqual(swapState("water", "en-ctd", null), { text: "water", direction: "ctd-en" });
  assert.deepEqual(swapState("water", "ctd-en", "   "), { text: "water", direction: "en-ctd" });
});

test("swapping twice returns to the starting direction", () => {
  const once = swapState("water", "en-ctd", "ZOMI_PLACEHOLDER");
  const twice = swapState(once.text, once.direction, "water");
  assert.deepEqual(twice, { text: "water", direction: "en-ctd" });
});
