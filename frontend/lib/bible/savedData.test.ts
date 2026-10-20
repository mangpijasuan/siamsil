import assert from "node:assert/strict";
import { test } from "node:test";
import { emptySavedData, NOTE_MAX_LENGTH, parseSavedData, refKey, saveNote, setHighlight, shareText, sortedByDate, toggleBookmark } from "./savedData.ts";

const ref = { version: "tdb", book: 1, chapter: 1, verse: 3, label: "Piancilna 1:3" };
const T1 = "2026-10-18T10:00:00.000Z";
const T2 = "2026-10-18T11:00:00.000Z";

test("bookmarks toggle and never duplicate", () => {
  let data = toggleBookmark(emptySavedData(), ref, T1);
  assert.equal(Object.keys(data.bookmarks).length, 1);
  assert.equal(data.bookmarks[refKey(ref)].createdAt, T1);
  data = toggleBookmark(data, ref, T2);
  assert.equal(Object.keys(data.bookmarks).length, 0);
});

test("bookmarks keep version, book, chapter and verse", () => {
  const data = toggleBookmark(emptySavedData(), { ...ref, version: "tb77" }, T1);
  const saved = Object.values(data.bookmarks)[0];
  assert.deepEqual([saved.version, saved.book, saved.chapter, saved.verse], ["tb77", 1, 1, 3]);
});

test("highlights add, change colour and remove", () => {
  let data = setHighlight(emptySavedData(), ref, "gold", T1);
  assert.equal(data.highlights[refKey(ref)].color, "gold");
  data = setHighlight(data, ref, "green", T2);
  assert.equal(data.highlights[refKey(ref)].color, "green");
  data = setHighlight(data, ref, "green", T2); // same colour again removes it
  assert.equal(data.highlights[refKey(ref)], undefined);
  data = setHighlight(setHighlight(data, ref, "blue", T1), ref, null, T2);
  assert.equal(data.highlights[refKey(ref)], undefined);
});

test("notes are trimmed plain text, keep their first date, and empty text deletes", () => {
  let data = saveNote(emptySavedData(), ref, "  <b>Read</b> again \r\n", T1);
  assert.equal(data.notes[refKey(ref)].text, "<b>Read</b> again"); // stored as text, never rendered as HTML
  data = saveNote(data, ref, "Edited", T2);
  assert.equal(data.notes[refKey(ref)].createdAt, T1);
  assert.equal(data.notes[refKey(ref)].updatedAt, T2);
  assert.equal(saveNote(data, ref, "x".repeat(NOTE_MAX_LENGTH + 50), T2).notes[refKey(ref)].text.length, NOTE_MAX_LENGTH);
  assert.equal(saveNote(data, ref, "   ", T2).notes[refKey(ref)], undefined);
});

test("saved data survives a round trip through storage", () => {
  let data = toggleBookmark(emptySavedData(), ref, T1);
  data = setHighlight(data, ref, "rose", T1);
  data = saveNote(data, ref, "Note", T1);
  assert.deepEqual(parseSavedData(JSON.stringify(data)), data);
});

test("corrupt storage is ignored entry by entry", () => {
  assert.deepEqual(parseSavedData("{not json"), emptySavedData());
  assert.deepEqual(parseSavedData("null"), emptySavedData());
  assert.deepEqual(parseSavedData("[]"), emptySavedData());
  const raw = JSON.stringify({
    bookmarks: { a: { ...ref, createdAt: T1 }, b: { version: "tdb" } },
    highlights: { c: { ...ref, color: "purple", updatedAt: T1 } },
    notes: { d: { ...ref, text: "  ", createdAt: T1, updatedAt: T1 } },
  });
  const data = parseSavedData(raw);
  assert.equal(Object.keys(data.bookmarks).length, 1);
  assert.equal(Object.keys(data.highlights).length, 0);
  assert.equal(Object.keys(data.notes).length, 0);
  assert.deepEqual(parseSavedData(JSON.stringify({ bookmarks: { bad: { ...ref, verse: -1, createdAt: T1 } } })), emptySavedData());
});

test("newest first", () => {
  const items = [{ createdAt: T1 }, { createdAt: T2 }];
  assert.deepEqual(sortedByDate(items).map((item) => item.createdAt), [T2, T1]);
});

test("copied and shared text carries the reference and version", () => {
  assert.equal(shareText("A kipat cilin…", "Piancilna 1:1", "TDB"), "A kipat cilin…\n— Piancilna 1:1 (TDB)");
});
