import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/site";

const title = "Zomi Language (Zopau and Tedim Chin)";
const description = "A reference guide to Zomi as used on Siamsil, including the names Zopau, Zolai, and Tedim Chin, where the language is spoken, and how it is written.";

export const metadata: Metadata = {
  title,
  description,
  ...(SITE_URL ? { alternates: { canonical: `${SITE_URL}/zomi-language` } } : {}),
  openGraph: { type: "article", title, description, siteName: "Siamsil" },
};

export default function ZomiLanguagePage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
      <article aria-labelledby="zomi-language-title" className="space-y-8 leading-relaxed">
        <header className="space-y-4">
          <h1 id="zomi-language-title" className="font-playfair text-4xl font-bold leading-tight sm:text-5xl">
            {title}
          </h1>
          <p className="text-lg">
            On Siamsil, <strong>Zomi</strong> refers to the language also known as <strong>Tedim Chin</strong> or{" "}
            <strong>Tiddim Chin</strong>, a Kuki-Chin language of western Myanmar and northeastern India.
            Its ISO 639-3 code is <code>ctd</code>. <a className="underline" href="#source-otsuka">[1]</a>{" "}
            <a className="underline" href="#source-glottolog">[2]</a>
          </p>
        </header>

        <section className="space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">Names and usage</h2>
          <p>
            Linguist Kosei Otsuka records <i lang="ctd">Zopau</i> and <i lang="ctd">Zolai</i> as local names
            in Tedim and Tonzang. The Digital Bible Society also lists <i>Zomi</i> as an alternate name for
            Tedim Chin. In broader contexts, <i>Zomi</i> can refer to a community identity. The language
            code helps readers identify the variety described here. <a className="underline" href="#source-otsuka">[1]</a>{" "}
            <a className="underline" href="#source-dbs">[3]</a>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">Where it is spoken</h2>
          <p>
            Otsuka describes Tedim Chin as spoken in Chin State and Sagaing Region in Myanmar and in
            Manipur and Mizoram in India. In Tedim and Tonzang townships, it serves as a lingua franca,
            a language people can use to communicate across communities.{" "}
            <a className="underline" href="#source-otsuka">[1]</a>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">Writing and grammar</h2>
          <p>
            The language has a Latin-based writing system developed by Joseph Herbert Cope in the early
            twentieth century. Otsuka describes three contrastive tones and notes that verbs usually
            come at the end of the clause. Many verbs have two stem forms whose use depends on the
            grammatical context. <a className="underline" href="#source-otsuka">[1]</a>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">References</h2>
          <ol className="list-decimal space-y-2 pl-6">
            <li id="source-otsuka">
              Kosei Otsuka (2014). <a className="underline" href="https://hdl.handle.net/10108/88511">“Tiddim Chin.”</a>{" "}
              <cite>Grammatical Sketches from the Field</cite>, volume 2, pp. 109–141.
              Tokyo University of Foreign Studies.
            </li>
            <li id="source-glottolog">
              Glottolog. <a className="underline" href="https://glottolog.org/resource/languoid/id/tedi1235">Tedim Chin (tedi1235)</a>.
            </li>
            <li id="source-dbs">
              Digital Bible Society. <a className="underline" href="https://arc.dbs.org/data/languages/ctd/">Tedim Chin language catalog</a>.
            </li>
          </ol>
        </section>

        <nav aria-label="Explore Zomi on Siamsil" className="flex flex-wrap gap-x-6 gap-y-2">
          <Link className="underline" href="/zomidictionary">Zomi dictionary</Link>
          <Link className="underline" href="/learning">Zomi lessons</Link>
          <Link className="underline" href="/library">Siamsil Library</Link>
        </nav>
      </article>
    </main>
  );
}
