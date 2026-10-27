import assert from "node:assert/strict";
import { test } from "node:test";

import { completeTrailingWord, completionPrefix, trailingWord, usefulCompletions } from "./wordComplete.ts";

// Placeholder words only: these tests check text handling, not Zomi.

test("the word being typed is found at the end of the text", () => {
  assert.deepEqual(trailingWord("abc def"), { start: 4, word: "def" });
  assert.deepEqual(trailingWord("ki-qa"), { start: 0, word: "ki-qa" });
  assert.deepEqual(trailingWord("qe’n"), { start: 0, word: "qe’n" });
  assert.equal(trailingWord("abc "), null);
  assert.equal(trailingWord("abc,"), null);
  assert.equal(trailingWord(""), null);
});

test("completion starts from two letters", () => {
  assert.equal(completionPrefix("abc d"), null);
  assert.equal(completionPrefix("abc de"), "de");
  assert.equal(completionPrefix("abc de "), null);
});

test("completing replaces only the word being typed", () => {
  assert.equal(completeTrailingWord("Abc de", "Defg"), "Abc Defg ");
  assert.equal(completeTrailingWord("Abc, de", "deqo"), "Abc, deqo ");
  assert.equal(completeTrailingWord("abc ", "deqo"), "abc deqo ");
});

test("suggestions skip duplicates and the word already typed", () => {
  assert.deepEqual(usefulCompletions(["Qamo", "qamo", "Qam", "qamel", "qamelpi"], "qam", 2), ["Qamo", "qamel"]);
  assert.deepEqual(usefulCompletions([], "qa"), []);
});
