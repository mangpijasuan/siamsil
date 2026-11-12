import type { ReactNode } from "react";

/** A plain reading page for About, Help and Resources. Only statements the project can stand behind. */
export default function InfoPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode }) {
  return (
    <article className="st-doc">
      <header className="st-doc-head">
        <p className="st-doc-eyebrow">{eyebrow}</p>
        <h1 className="font-playfair">{title}</h1>
        <p>{intro}</p>
      </header>
      <div className="st-doc-body">{children}</div>
    </article>
  );
}
