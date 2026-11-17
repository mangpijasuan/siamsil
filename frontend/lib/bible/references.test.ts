import assert from "node:assert/strict";
import { test } from "node:test";
import { adjacentChapters, alignVerses, bibleHref, chooseCompanion, filterBooks, formatReference, NO_COMPARE, readingMode, readingModeTargets } from "./references.ts";

const books = [
  { book_id: 1, code: "GEN", name: "Genesis", name_local: "Piancilna", chapters: [1, 2, 3] },
  { book_id: 2, code: "EXO", name: "Exodus", name_local: "Paikhiatna", chapters: [11, 12] }, // TB77 lacks Exodus 1-10
  { book_id: 40, code: "MAT", name: "Matthew", name_local: "Matthai", chapters: [1] },
];

test("next and previous stay inside a book", () => {
  assert.deepEqual(adjacentChapters(books, 1, 2), { previous: { book: 1, chapter: 1 }, next: { book: 1, chapter: 3 } });
});

test("navigation crosses into the neighbouring book and only to chapters that exist", () => {
  assert.deepEqual(adjacentChapters(books, 1, 3).next, { book: 2, chapter: 11 });
  assert.deepEqual(adjacentChapters(books, 2, 11).previous, { book: 1, chapter: 3 });
  assert.deepEqual(adjacentChapters(books, 2, 12).next, { book: 40, chapter: 1 });
});

test("no links past either end or for unknown chapters", () => {
  assert.equal(adjacentChapters(books, 1, 1).previous, null);
  assert.equal(adjacentChapters(books, 40, 1).next, null);
  assert.deepEqual(adjacentChapters(books, 2, 5), { previous: null, next: null });
  assert.deepEqual(adjacentChapters(books, 99, 1), { previous: null, next: null });
});

test("verses align by number, in order, keeping verses only one side has", () => {
  const rows = alignVerses(
    [{ verse: 2, label: "2", text: "b" }, { verse: 1, label: "1", text: "a" }],
    [{ verse: 1, label: "1", text: "A" }, { verse: 3, label: "3", text: "C" }],
  );
  assert.deepEqual(rows.map((row) => row.verse), [1, 2, 3]);
  assert.equal(rows[0].secondary[0].text, "A");
  assert.deepEqual(rows[1].secondary, []);
  assert.deepEqual(rows[2].primary, []);
  assert.equal(rows[2].label, "3");
});

test("a joined verse (TDB Genesis 1:17-18) takes in both English verses, text untouched", () => {
  const rows = alignVerses(
    [{ verse: 16, label: "16", text: "z16" }, { verse: 17, label: "17-18", text: "z17-18" }, { verse: 19, label: "19", text: "z19" }],
    [{ verse: 16, label: "16", text: "e16" }, { verse: 17, label: "17", text: "e17" }, { verse: 18, label: "18", text: "e18" }, { verse: 19, label: "19", text: "e19" }],
  );
  assert.deepEqual(rows.map((row) => row.label), ["16", "17-18", "19"]);
  assert.deepEqual(rows[1].primary.map((v) => v.text), ["z17-18"]);
  assert.deepEqual(rows[1].secondary.map((v) => v.text), ["e17", "e18"]);
});

test("joins on the second version are handled the same way", () => {
  const rows = alignVerses(
    [{ verse: 4, label: "4", text: "z4" }, { verse: 5, label: "5", text: "z5" }],
    [{ verse: 4, label: "4-5", text: "e4-5" }],
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].label, "4-5");
  assert.deepEqual(rows[0].primary.map((v) => v.text), ["z4", "z5"]);
});

test("links keep the version and the compared version", () => {
  assert.equal(bibleHref({ v: "tdb", compare: "web", book: 1, chapter: 2 }), "/bible?v=tdb&compare=web&book=1&chapter=2");
  assert.equal(bibleHref({ v: "tdb", compare: NO_COMPARE, book: 1, chapter: 2 }, 5), "/bible?v=tdb&compare=none&book=1&chapter=2#v5");
  assert.equal(bibleHref({ v: "kjv", compare: null }), "/bible?v=kjv");
});

test("references read naturally", () => {
  assert.equal(formatReference("Piancilna", 1, "3"), "Piancilna 1:3");
  assert.equal(formatReference("Piancilna", 1), "Piancilna 1");
});

const versions = [
  { id: "tdb", abbreviation: "TDB", language_iso: "ctd" },
  { id: "kjv", abbreviation: "KJV", language_iso: "eng" },
  { id: "web", abbreviation: "WEB", language_iso: "eng" },
];

test("a Zomi version is paired with English by default, WEB first", () => {
  assert.equal(chooseCompanion(versions, versions[0], undefined)?.id, "web");
});

test("an explicit compare wins, 'none' turns it off, unknown or same version gives none", () => {
  assert.equal(chooseCompanion(versions, versions[0], "kjv")?.id, "kjv");
  assert.equal(chooseCompanion(versions, versions[0], NO_COMPARE), null);
  assert.equal(chooseCompanion(versions, versions[0], "xyz"), null);
  assert.equal(chooseCompanion(versions, versions[0], "tdb"), null);
});

test("an English main version gets no default companion", () => {
  assert.equal(chooseCompanion(versions, versions[2], undefined), null);
});

test("URL-selected versions, not stale device preferences, determine reading mode", () => {
  assert.equal(readingMode(versions[0], versions[2]), "both");
  assert.equal(readingMode(versions[0], null), "zomi");
  assert.equal(readingMode(versions[2], null), "english");
  assert.deepEqual(readingModeTargets(versions, versions[0], versions[2]), { zomi: versions[0], english: versions[2] });
  assert.deepEqual(readingModeTargets(versions, versions[2], null), { zomi: versions[0], english: versions[2] });
});

test("book search matches Zomi names, English names and codes", () => {
  assert.deepEqual(filterBooks(books, "pian").map((b) => b.book_id), [1]);
  assert.deepEqual(filterBooks(books, "exo").map((b) => b.book_id), [2]);
  assert.deepEqual(filterBooks(books, "MAT").map((b) => b.book_id), [40]);
  assert.equal(filterBooks(books, "  ").length, 3);
});
