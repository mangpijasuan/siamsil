"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { IconArrow, IconBook, IconCross, IconSearch, IconTranslate } from "@/components/Icons";
import { bibleHref } from "@/lib/bible/references";
import {
  clearSearches,
  clearWorkspace,
  emptyWorkspace,
  exportWorkspace,
  isEmpty,
  readWorkspace,
  removeSavedWord,
  type Workspace,
} from "@/lib/workspace";

function when(at: number | string) {
  const date = typeof at === "number" ? new Date(at) : new Date(at);
  return Number.isNaN(date.getTime()) || !date.getTime() ? "" : date.toLocaleDateString();
}

function Section({ title, action, children, id }: { title: string; action?: React.ReactNode; children: React.ReactNode; id: string }) {
  return (
    <section className="ws-panel" aria-labelledby={id}>
      <div className="ws-panel-head"><h2 id={id}>{title}</h2>{action}</div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="ws-empty">{children}</p>;
}

export default function WorkspaceClient() {
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(() => {
    try {
      setWorkspace(readWorkspace(window.localStorage));
    } catch {
      setWorkspace(emptyWorkspace());
      setMessage("This browser is not letting Siamsil store anything (private browsing or blocked storage).");
    }
    setReady(true);
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(refresh);
    window.addEventListener("storage", refresh); // another tab saved a word or a bookmark
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("storage", refresh);
    };
  }, [refresh]);

  function download() {
    const data = exportWorkspace(window.localStorage);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `siamsil-workspace-${data.exported_at.slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setMessage("Your workspace was downloaded as a file.");
  }

  function clearAll() {
    if (!window.confirm("Remove your saved words, searches, Bible bookmarks, notes, highlights and learning progress from this browser? Reading settings are kept. This cannot be undone.")) return;
    clearWorkspace(window.localStorage);
    refresh();
    setMessage("Your workspace was cleared from this browser.");
  }

  const { savedWords, searches, recentChapters, bookmarks, notes, highlights, learning } = workspace;
  const stats = [
    { label: "Saved words", value: savedWords.length },
    { label: "Recent searches", value: searches.length },
    { label: "Bible bookmarks", value: bookmarks.length },
    { label: "Notes and highlights", value: notes.length + highlights },
    { label: "Learning XP", value: learning.xp },
  ];

  return (
    <div className="ws">
      <header className="ws-header">
        <p className="ws-eyebrow">My Workspace</p>
        <h1 className="font-playfair">Your Zomi, in one place</h1>
        <p className="ws-lede">
          Saved words, searches, Bible bookmarks and learning progress. Everything here is kept <strong>in this browser only</strong>:
          Siamsil has no copy, and accounts with sync are not available yet.
        </p>
      </header>

      <dl className="ws-stats" aria-label="Workspace summary">
        {stats.map((stat) => (
          <div className="ws-stat" key={stat.label}><dd>{ready ? stat.value.toLocaleString() : "–"}</dd><dt>{stat.label}</dt></div>
        ))}
      </dl>

      {ready && isEmpty(workspace) && (
        <div className="ws-start">
          <h2 className="font-playfair">Start your workspace</h2>
          <p>Nothing is saved yet. Save a word in the dictionary, search or translate, bookmark a verse, or practice a lesson, and it appears here.</p>
          <div className="ws-start-links">
            <Link href="/zomidictionary"><IconBook size={17} /> Dictionary</Link>
            <Link href="/zomitranslate"><IconTranslate size={17} /> Translate</Link>
            <Link href="/bible"><IconCross size={17} /> Bible</Link>
            <Link href="/learning"><IconArrow size={17} /> Learn</Link>
          </div>
        </div>
      )}

      <div className="ws-grid">
        <Section id="ws-words" title="Saved words" action={<Link href="/zomidictionary">Dictionary →</Link>}>
          {savedWords.length === 0 ? <Empty>Use the save button on a dictionary entry to keep it here.</Empty> : (
            <ul className="ws-list">
              {savedWords.map((word) => (
                <li key={word.id}>
                  <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="ws-item">
                    <strong className="font-playfair">{word.english}</strong>
                    {word.zomi && <span lang="ctd">{word.zomi}</span>}
                  </Link>
                  <button type="button" className="ws-remove" aria-label={`Remove ${word.english}`}
                    onClick={() => setWorkspace({ ...workspace, savedWords: removeSavedWord(window.localStorage, word.id) })}>Remove</button>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section id="ws-searches" title="Recent searches"
          action={searches.length > 0 && <button type="button" className="ws-link-button" onClick={() => { clearSearches(window.localStorage); refresh(); }}>Clear</button>}>
          {searches.length === 0 ? <Empty>Your dictionary and translation searches will be listed here.</Empty> : (
            <ul className="ws-list">
              {searches.map((search) => (
                <li key={`${search.kind}:${search.query}`}>
                  <Link className="ws-item ws-item-row"
                    href={search.kind === "dictionary" ? `/zomidictionary?q=${encodeURIComponent(search.query)}` : `/zomitranslate?q=${encodeURIComponent(search.query)}`}>
                    {search.kind === "dictionary" ? <IconSearch size={15} /> : <IconTranslate size={15} />}
                    <span className="ws-query">{search.query}</span>
                    <small>{search.kind === "dictionary" ? "Dictionary" : "Translate"}{when(search.at) && ` · ${when(search.at)}`}</small>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section id="ws-bible" title="Bible" action={<Link href="/bible">Open Bible →</Link>}>
          {recentChapters.length === 0 && bookmarks.length === 0 && notes.length === 0
            ? <Empty>Chapters you read, verses you bookmark and notes you write in the Bible reader appear here.</Empty> : (
              <>
                {recentChapters.length > 0 && <>
                  <h3>Continue reading</h3>
                  <ul className="ws-list">
                    {recentChapters.slice(0, 4).map((chapter) => (
                      <li key={`${chapter.v}:${chapter.book}`}>
                        <Link className="ws-item ws-item-row" href={bibleHref({ v: chapter.v, book: chapter.book, chapter: chapter.chapter })}>
                          <IconCross size={15} /><span className="ws-query">{chapter.bookName} {chapter.chapter}</span><small>{chapter.version}</small>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </>}
                {bookmarks.length > 0 && <>
                  <h3>Bookmarks</h3>
                  <ul className="ws-list">
                    {bookmarks.slice(0, 8).map((mark) => (
                      <li key={`${mark.version}:${mark.book}:${mark.chapter}:${mark.verse}`}>
                        <Link className="ws-item ws-item-row" href={bibleHref({ v: mark.version, book: mark.book, chapter: mark.chapter }, mark.verse)}>
                          <span className="ws-query">{mark.label}</span><small>{mark.version.toUpperCase()}</small>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </>}
                {notes.length > 0 && <>
                  <h3>Notes</h3>
                  <ul className="ws-list">
                    {notes.slice(0, 5).map((note) => (
                      <li key={`${note.version}:${note.book}:${note.chapter}:${note.verse}`}>
                        <Link className="ws-item" href={bibleHref({ v: note.version, book: note.book, chapter: note.chapter }, note.verse)}>
                          <strong>{note.label}</strong><span className="ws-note">{note.text}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </>}
              </>
            )}
        </Section>

        <Section id="ws-learning" title="Learning" action={<Link href="/learning">Practice →</Link>}>
          {learning.xp === 0 && learning.streak === 0 ? <Empty>Practice reviewed phrases in Learn to build your streak.</Empty> : (
            <div className="ws-learning">
              <div><strong className="font-playfair">{learning.streak}</strong><span>day streak</span></div>
              <div><strong className="font-playfair">{learning.xp.toLocaleString()}</strong><span>XP</span></div>
            </div>
          )}
        </Section>
      </div>

      <section className="ws-panel ws-data" aria-labelledby="ws-data">
        <div className="ws-panel-head"><h2 id="ws-data">Your data</h2></div>
        <p>
          Siamsil does not collect your workspace. It lives in this browser, so it does not follow you to another device, and clearing
          the browser&apos;s site data removes it. Download a copy to keep it.
        </p>
        <div className="ws-actions">
          <button type="button" className="ws-button" onClick={download} disabled={!ready}>Download my data</button>
          <button type="button" className="ws-button ws-button-quiet" onClick={clearAll} disabled={!ready || isEmpty(workspace)}>Clear workspace</button>
        </div>
        <p className="ws-status" role="status" aria-live="polite">{message}</p>
      </section>
    </div>
  );
}
