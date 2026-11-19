import assert from "node:assert/strict";
import { test } from "node:test";

import {
  clearSearches,
  clearWorkspace,
  DATA_KEYS,
  exportWorkspace,
  isEmpty,
  readWorkspace,
  removeSavedWord,
  type StorageLike,
} from "./workspace.ts";

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    get length() { return data.size; },
    key: (index) => [...data.keys()][index] ?? null,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => { data.set(key, value); },
    removeItem: (key) => { data.delete(key); },
  };
}

const filled = () => memoryStorage({
  "siamsil.saved-words": JSON.stringify([{ id: 1, english: "water", zomi: "ZOMI_WATER" }, { id: 2, english: "family", zomi: null }]),
  "siamsil.search-history": JSON.stringify([{ kind: "dictionary", query: "water", at: 2 }, { kind: "translate", query: "thank you", at: 1 }]),
  "siamsil.bible-recent": JSON.stringify([{ v: "tdb", version: "TDB", book: 43, bookName: "Johan", chapter: 3 }]),
  "siamsil.bible.saved": JSON.stringify({
    schema: 1,
    bookmarks: {
      a: { version: "tdb", book: 1, chapter: 1, verse: 1, label: "Gen 1:1", createdAt: "2026-11-01T00:00:00Z" },
      b: { version: "tdb", book: 43, chapter: 3, verse: 16, label: "John 3:16", createdAt: "2026-11-02T00:00:00Z" },
    },
    highlights: { c: { version: "tdb", book: 1, chapter: 1, verse: 2, label: "x", color: "gold" } },
    notes: { d: { version: "tdb", book: 1, chapter: 1, verse: 3, label: "Gen 1:3", text: "A note", updatedAt: "2026-11-03T00:00:00Z" } },
  }),
  "siamsil_streak": "4",
  "siamsil_xp": "120",
  "siamsil.bible.preferences": JSON.stringify({ size: 18 }),
  "unrelated": "keep",
});

test("reads every part of the workspace", () => {
  const workspace = readWorkspace(filled());
  assert.deepEqual(workspace.savedWords.map((w) => w.english), ["water", "family"]);
  assert.equal(workspace.searches.length, 2);
  assert.equal(workspace.recentChapters[0].bookName, "Johan");
  assert.deepEqual(workspace.bookmarks.map((b) => b.label), ["John 3:16", "Gen 1:1"]); // newest first
  assert.equal(workspace.notes[0].text, "A note");
  assert.equal(workspace.highlights, 1);
  assert.deepEqual(workspace.learning, { streak: 4, xp: 120 });
  assert.equal(isEmpty(workspace), false);
});

test("damaged or missing data never breaks the workspace", () => {
  const storage = memoryStorage({
    "siamsil.saved-words": "{not json",
    "siamsil.search-history": JSON.stringify([{ kind: "other", query: "x" }, null, { kind: "translate", query: "ok" }]),
    "siamsil.bible.saved": JSON.stringify({ bookmarks: { a: { version: "tdb", label: "no numbers" } } }),
    "siamsil_xp": "-5",
  });
  const workspace = readWorkspace(storage);
  assert.equal(workspace.savedWords.length, 0);
  assert.deepEqual(workspace.searches.map((s) => s.query), ["ok"]);
  assert.equal(workspace.bookmarks.length, 0);
  assert.equal(workspace.learning.xp, 0);
  assert.equal(isEmpty(readWorkspace(memoryStorage())), true);
});

test("export holds every Siamsil item and nothing else", () => {
  const exported = exportWorkspace(filled(), new Date("2026-11-19T12:00:00Z"));
  assert.equal(exported.format, "siamsil-workspace");
  assert.equal(exported.exported_at, "2026-11-19T12:00:00.000Z");
  assert.ok("siamsil.bible.preferences" in exported.items);
  assert.ok("siamsil_xp" in exported.items);
  assert.ok(!("unrelated" in exported.items));
  assert.deepEqual(Object.keys(exported.items), [...Object.keys(exported.items)].sort());
});

test("clear removes the person's data but keeps reading settings and other sites' keys", () => {
  const storage = filled();
  const removed = clearWorkspace(storage);
  assert.deepEqual([...removed].sort(), [...DATA_KEYS].sort());
  assert.ok(storage.data.has("siamsil.bible.preferences"));
  assert.ok(storage.data.has("unrelated"));
  assert.equal(isEmpty(readWorkspace(storage)), true);
});

test("remove one saved word, or the search history only", () => {
  const storage = filled();
  assert.deepEqual(removeSavedWord(storage, 1).map((w) => w.id), [2]);
  assert.deepEqual(readWorkspace(storage).savedWords.map((w) => w.id), [2]);
  clearSearches(storage);
  const workspace = readWorkspace(storage);
  assert.equal(workspace.searches.length, 0);
  assert.equal(workspace.savedWords.length, 1);
});
