import type { Metadata } from "next";
import Link from "next/link";
import InfoPage from "@/components/InfoPage";

export const metadata: Metadata = {
  title: "Help",
  description: "How to search the Siamsil dictionary, find translations, read the Bible and understand the labels.",
  alternates: { canonical: "/help" },
};

export default function HelpPage() {
  return (
    <InfoPage eyebrow="Help" title="Using Siamsil" intro="Short answers to the most common questions.">
      <section>
        <h2>Finding a word</h2>
        <p>Type an English or Zomi word in the search box at the top of any page, or use the <Link href="/zomidictionary">Dictionary</Link>. Try <Link href="/zomidictionary?q=water">water</Link> or <Link href="/zomidictionary?q=family">family</Link>.</p>
      </section>
      <section>
        <h2>Finding a translation</h2>
        <p><Link href="/zomitranslate">Translate</Link> looks for pairs Siamsil already holds, such as dictionary entries, reviewed phrases and Bible verses. If it has nothing, it says so; it does not make up Zomi.</p>
      </section>
      <section>
        <h2>What “unreviewed” means</h2>
        <p>The entry or translation has not yet been checked by a Zomi reviewer. It may be right, but treat it with care.</p>
      </section>
      <section>
        <h2>Reading the Bible</h2>
        <p>Open the <Link href="/bible">Bible</Link>, choose a version, book and chapter, or search for a word. Reading size and theme can be changed in the reader.</p>
      </section>
      <section>
        <h2>Your saved words</h2>
        <p>Saved words and search history are kept on this device only. Clearing your browser data removes them.</p>
      </section>
    </InfoPage>
  );
}
