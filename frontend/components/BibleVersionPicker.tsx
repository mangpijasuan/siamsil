"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import type { BibleVersionInfo } from "@/lib/api";

function optionLabel(version: BibleVersionInfo) {
  return `${version.abbreviation.toUpperCase()} · ${version.name}${version.language_name ? ` (${version.language_name})` : ""}`;
}

export default function BibleVersionPicker({
  versions,
  version,
  compare,
  book,
  chapter,
}: {
  versions: BibleVersionInfo[];
  version: string;
  compare: string;
  book?: number;
  chapter: number;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function go(nextVersion: string, nextCompare: string) {
    const query = new URLSearchParams({ v: nextVersion });
    if (nextCompare && nextCompare !== nextVersion) query.set("compare", nextCompare);
    if (book) {
      query.set("book", String(book));
      query.set("chapter", String(chapter));
    }
    startTransition(() => router.push(`/bible?${query.toString()}`));
  }

  return (
    <div className={`bv-picker${pending ? " is-pending" : ""}`}>
      <label className="bv-field">
        <span className="gold-label">Version</span>
        <select value={version} onChange={(event) => go(event.target.value, compare)}>
          {versions.map((item) => <option key={item.id} value={item.id}>{optionLabel(item)}</option>)}
        </select>
      </label>
      <label className="bv-field">
        <span className="gold-label">Compare with</span>
        <select value={compare} onChange={(event) => go(version, event.target.value)}>
          <option value="">None</option>
          {versions.filter((item) => item.id !== version).map((item) => (
            <option key={item.id} value={item.id}>{optionLabel(item)}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
