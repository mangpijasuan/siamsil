import type { Metadata } from "next";
import Link from "next/link";
import InfoPage from "@/components/InfoPage";

export const metadata: Metadata = {
  title: "About",
  description: "Siamsil is the digital home for the Zomi language: a dictionary, a Bible reader, stored translations and reviewed learning phrases.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <InfoPage eyebrow="About" title="Siamsil" intro="The digital home for the Zomi language and community.">
      <section>
        <h2>What you can do today</h2>
        <ul>
          <li><Link href="/zomidictionary">Dictionary</Link>: look up English and Zomi words.</li>
          <li><Link href="/zomitranslate">Translate</Link>: find translations Siamsil already holds. It retrieves stored pairs; it does not write new Zomi.</li>
          <li><Link href="/bible">Bible</Link>: read and search the Zomi Bible versions Siamsil may display.</li>
          <li><Link href="/learning">Learn</Link>: everyday phrases that Zomi teachers have reviewed.</li>
          <li><Link href="/chat">Siamsil AI</Link>: answers drawn from the sources above, with the source shown.</li>
        </ul>
      </section>
      <section>
        <h2>How Siamsil treats language data</h2>
        <ul>
          <li>Machine-made translations are labelled <strong>unreviewed</strong>. The large example-sentence collection has its Zomi side written by a machine from English sentences, and is not treated as correct.</li>
          <li>Only people decide what counts as correct Zomi. Siamsil does not approve its own translations.</li>
          <li>Every source has a recorded permission status. Text Siamsil may not show or train on is kept out.</li>
          <li>Your saved words and search history stay on your device.</li>
        </ul>
      </section>
      <section>
        <h2>Still to come</h2>
        <p>Phone apps for iOS and Android are planned and are not built yet.</p>
      </section>
    </InfoPage>
  );
}
