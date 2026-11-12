import type { Metadata } from "next";
import Link from "next/link";
import InfoPage from "@/components/InfoPage";

export const metadata: Metadata = {
  title: "Resources",
  description: "What Siamsil holds, and how each collection is labelled.",
  alternates: { canonical: "/resources" },
};

const COLLECTIONS = [
  { href: "/zomidictionary", name: "Dictionary", note: "The English–Zomi master of about 20,000 entries. Entries not yet checked by a reviewer are labelled." },
  { href: "/zomitranslate", name: "Example sentences", note: "English sentences from Tatoeba/OPUS with a machine-written Zomi side. Unreviewed; not ground truth." },
  { href: "/bible", name: "Bible", note: "Zomi Bible versions that Siamsil is allowed to display." },
  { href: "/learning", name: "Learning phrases", note: "Everyday phrases already reviewed by Zomi teachers, and citizenship-test practice." },
  { href: "/library", name: "Library", note: "Books and cultural collections. Some shelves are planned and marked as such." },
];

export default function ResourcesPage() {
  return (
    <InfoPage eyebrow="Resources" title="What Siamsil holds" intro="Each collection and how it is labelled.">
      <section>
        <ul className="st-doc-list">
          {COLLECTIONS.map((item) => (
            <li key={item.href}><Link href={item.href}>{item.name}</Link><span>{item.note}</span></li>
          ))}
        </ul>
      </section>
      <section>
        <p>The sources and their permission status are recorded in the project&apos;s data rights register. Siamsil shows only what it is allowed to show.</p>
      </section>
    </InfoPage>
  );
}
