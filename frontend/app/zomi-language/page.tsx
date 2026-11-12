import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/site";

const title = "Zomi Language (Zopau and Tedim Chin)";
const description = "A reference guide to Zomi as used on Siamsil, covering spoken Zopau, the Zolai literary tradition, and the language known as Tedim Chin.";

export const metadata: Metadata = {
  title,
  description,
  ...(SITE_URL ? { alternates: { canonical: `${SITE_URL}/zomi-language` } } : {}),
  openGraph: { type: "article", title, description, siteName: "Siamsil" },
};

function Citations({ numbers }: { numbers: number[] }) {
  return (
    <span className="inline-flex flex-wrap gap-x-1 text-sm">
      {numbers.map((number) => (
        <a key={number} className="underline" href={`#source-${number}`} aria-label={`Reference ${number}`}>
          [{number}]
        </a>
      ))}
    </span>
  );
}

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
            Its ISO 639-3 code is <code>ctd</code>. <Citations numbers={[1, 2]} />
          </p>
        </header>

        <nav aria-label="Article contents" className="space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">Contents</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            <li><a className="underline" href="#names">Names, scope, and identity</a></li>
            <li><a className="underline" href="#geography">Where Zopau is spoken</a></li>
            <li><a className="underline" href="#classification">Language family and local variation</a></li>
            <li><a className="underline" href="#pronunciation">Sound, tone, and pronunciation</a></li>
            <li><a className="underline" href="#grammar">Grammar in speech and writing</a></li>
            <li><a className="underline" href="#grammar-examples">Reading examples in a grammar</a></li>
            <li><a className="underline" href="#latin-script">The Latin writing tradition</a></li>
            <li><a className="underline" href="#pau-cin-hau">Pau Cin Hau and the Laipian tradition</a></li>
            <li><a className="underline" href="#literature">Zolai literature and translation</a></li>
            <li><a className="underline" href="#education">Education and public life</a></li>
            <li><a className="underline" href="#using-references">Using the references and building a record</a></li>
            <li><a className="underline" href="#references">References</a></li>
          </ul>
        </nav>

        <section id="names" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Names, scope, and identity</h2>
          <p>
            On Siamsil, Zopau is the spoken language and Zolai is its literature and written tradition. Tedim Chin, also written Tiddim Chin, is the name readers will encounter in many English-language grammars and catalogs. Zomi is the name Siamsil uses for the language in its dictionary and learning tools. A reader can therefore come to this article through a family name for the language, a search for literature, or a label found in a linguistic database. These entry points lead to different kinds of information about the same subject on Siamsil.{" "}
            <Citations numbers={[1, 2, 3]} />
          </p>
          <p>
            The distinction between Zopau and Zolai is particularly helpful when describing a resource. A recording of someone telling a story gives listeners an example of Zopau. An edited collection of stories gives readers an example of Zolai. A single story may belong to both settings over its lifetime. Someone can first tell it aloud, another person can transcribe it, an editor can prepare a reading edition, and a later reader can perform that edition aloud. Each version has its own history. Where several versions are available, identifying how each was made helps readers understand why their wording may differ.
          </p>
          <p>
            Otsuka records both terms in his description of speech in Tedim and Tonzang. His grammatical sketch uses Tiddim Chin as its English title. The Digital Bible Society lists Zomi among the alternative names for Tedim Chin. The same database uses a language identifier to bring editions and references together across their different titles. Readers looking for research can use both English spellings, alongside Zopau and the identifier ctd, to find records that a single search might miss.{" "}
            <Citations numbers={[1, 2, 3]} />
          </p>
          <p>
            Zomi also appears as a name for people and communities. In that setting the word can express a shared identity across communities with distinct speech traditions. When a source says Zomi, the surrounding discussion matters. A paper may be describing Tedim Chin grammar, a community organization may be describing the people it serves, and a public office may be naming an interpretation service. Those contexts answer different questions. This article uses the label for the Tedim Chin language on Siamsil, and describes community identity where the source itself concerns people.{" "}
            <Citations numbers={[2, 3, 4, 5]} />
          </p>
          <p>
            Language identifiers are useful for libraries and software because a short code can connect records with different display names. The ISO 639-3 code for Tedim Chin is ctd and the Glottolog identifier is tedi1235. A code can help a catalog distinguish this entry from those for related languages. A more detailed description of a recording can still include the name its speaker uses, the place or community they associate it with, and the setting in which they learned to speak it. The code provides a starting point for finding the item. Those other details tell a reader what kind of evidence the item contains.{" "}
            <Citations numbers={[2]} />
          </p>
        </section>

        <section id="geography" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Where Zopau is spoken</h2>
          <p>
            Zopau belongs to a region where languages and speech communities extend across administrative boundaries. Otsuka identifies Chin State and Sagaing Region in western Myanmar and Manipur and Mizoram in northeastern India as parts of the language’s geographic distribution. He describes Tedim Chin as a lingua franca in Tedim and Tonzang townships. In this setting a lingua franca is a language people can use to talk with one another across communities, including when they grew up speaking different local varieties. Its use for wider communication can coexist with the use of other languages within the same places.{" "}
            <Citations numbers={[1]} />
          </p>
          <p>
            The distinction between a place name and a language name helps when reading historical sources. Tiddim is an older spelling found in scholarship. Tedim names a place and appears in the name of the language. Tonzang is also a place, and the presence of Tedim Chin there is compatible with documentation of additional local languages. For example, Christopher Button’s comparative work lists a variety he calls Zo of Tonzang alongside Tedim and Sizang as separate entries in his material. The locality in a title is a clue to where material comes from. The author’s description and labels identify the speech being studied.{" "}
            <Citations numbers={[2, 6, 7]} />
          </p>
          <p>
            The Zomi Education Working Group describes its community work in Tedim, Tonzang, Kale, and Tamu. Its account helps locate educational activity and connections between northern Chin State and the neighboring valley communities. Its annual report describes work carried out during the pandemic and political unrest, including home-based learning materials and support for learning centers. This evidence is especially informative about where the organization worked and what it did. Otsuka’s description, which sets out to describe a language, provides a different type of geographic evidence.{" "}
            <Citations numbers={[1, 4, 8]} />
          </p>
          <p>
            A township report provides yet another view. The 2014 Myanmar census township report for Tedim presents demographic and socioeconomic information for residents of an administrative area. A count of residents answers a geographic question. A count of speakers would need to specify the language question asked, the area covered, and whether it measures first language, ability to speak, or language used at home. A count by ethnic identity uses its own definition. This article gives geographic descriptions where sources support them and leaves a single present-day worldwide speaker total unspecified.{" "}
            <Citations numbers={[1, 9]} />
          </p>
          <p>
            The language also has a public presence beyond its historical region. In Tulsa, materials connected with city services name Zopau or Zomi in contexts where residents need information in their own language. The evidence is local and concrete. It shows that public programs have recognized a language-access need, while family and community use also includes forms of conversation that a city document was never designed to measure. For readers tracing the language across locations, the most useful details are the dates, institutions, and purposes of the records they consult.{" "}
            <Citations numbers={[5, 10, 11]} />
          </p>
        </section>

        <section id="classification" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Language family and local variation</h2>
          <p>
            Linguists place Tedim Chin in the Kuki-Chin branch of the wider language family often called Sino-Tibetan or Tibeto-Burman in the literature relevant to this article. A family classification is a claim about historical relationships among languages. A subgroup is a proposal about a closer relationship within that family. Scholars compare multiple kinds of evidence, including recurring correspondences between sounds and patterns of shared change. The results can help explain why two related languages have words that look or sound alike, even though people may use different names for those languages today.{" "}
            <Citations numbers={[1, 2, 6, 12]} />
          </p>
          <p>
            Comparative research works at a different scale from a guide to everyday speech. Button’s study of Northern Chin examines relationships among a set of documented varieties. VanBik’s reconstruction of Proto-Kuki-Chin takes a broader historical perspective and uses evidence from multiple languages, including Tedim. A reconstructed form is an analytical proposal about an earlier stage of speech. Modern words in a dictionary can help provide evidence for such a proposal. A reconstruction belongs in a historical discussion, where readers can see how the author reached it and compare the evidence with other work.{" "}
            <Citations numbers={[6, 12]} />
          </p>
          <p>
            Glottolog gives Tedim Chin, Paite Chin, and Zou their own catalog entries. These distinctions are helpful for readers who encounter similar spellings or overlapping community labels. Paite and Zou can be discussed as related languages while the specific language covered here remains Tedim Chin. A reference to Zo or Zomi needs particular care because the spelling alone may leave the intended speech variety uncertain. Glottolog lists Zomi among the alternate names recorded for Zou, which it indexes under the code zom. An author’s location, language code, example material, and classification can resolve that uncertainty. Links to the relevant catalog entries give readers a way to check how a source has been indexed.{" "}
            <Citations numbers={[2, 6, 13, 14]} />
          </p>
          <p>
            Variation also occurs within the scope of a language entry. A conversation in one household, a reading for an audience, and a formal speech can differ in pronunciation, choice of words, and sentence structure. Geography is one source of variation, and the social setting of an utterance is another. Otsuka explicitly distinguishes his colloquial material from earlier work focused on written style. That distinction offers a practical way to read examples. Ask first whether an author recorded someone talking, analyzed a previously written text, or asked a speaker for a particular form. Each procedure can produce valuable material, and each gives the resulting example its context.{" "}
            <Citations numbers={[1, 15]} />
          </p>
          <p>
            For a learner or editor, local variation is often easiest to understand through attributed examples. A glossary can say where a form was recorded or where it was published. A lesson can identify the variety used in its audio. An archive can keep the speaker’s own description alongside the technical label used for search. This approach lets people compare varieties while respecting the labels they give their own speech. It also leaves room for related materials to be linked through places, topics, or language family information, so a reader can explore connections without having to infer them from a shared name.
          </p>
        </section>

        <section id="pronunciation" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Sound, tone, and pronunciation</h2>
          <p>
            A sound description begins by asking which differences matter to speakers. Some differences distinguish words or grammatical forms. Others come from the position of a sound, the neighboring sounds, or the way a person speaks in a given setting. For Tedim Chin, both Henderson’s descriptive study and Otsuka’s grammatical sketch give readers a path into the analysis of syllables and pronunciation. Henderson’s book includes chapters on spelling and pronunciation and on syllable structure. Otsuka also describes a system of three contrastive tones and changes in tone in connected speech.{" "}
            <Citations numbers={[1, 16]} />
          </p>
          <p>
            A syllable includes a vowel at its center and may have consonants around it. Linguists often use a compact notation to show which positions are possible. A learner can make sense of that notation by listening for the opening sound, the vowel, and what happens at the end. A spelling is designed for reading and writing within a convention. A phonetic transcription is designed to show details of sound. Both can be displayed with a recording because they serve different purposes. The spelling lets readers recognize the word in a text, and the transcription can help them locate a difference they hear.{" "}
            <Citations numbers={[1, 16]} />
          </p>
          <p>
            Tone involves differences in pitch that can help distinguish forms. The pitch of a syllable can also be affected by intonation, which operates across an utterance. A speaker may place emphasis on a word or change the way a question sounds. A reference that describes tone therefore pays attention to where a word occurs and what surrounds it. A good comparison for a learner is to hear a word by itself, then hear it in a short phrase and again in a longer sentence. The repeated example can make it easier to hear which features stay stable and which vary with the setting.{" "}
            <Citations numbers={[1, 16]} />
          </p>
          <p>
            Otsuka describes tone sandhi, a term for changes in tone associated with the sounds or forms around a syllable. The technical term is useful because it distinguishes a patterned change from an isolated recording difference. A beginner may hear a pitch pattern in a dictionary recording and a different realization in a story. The example sentence can reveal information about the environment in which the change occurs. Listening to several recordings also helps distinguish the effects of the surrounding phrase from the normal differences between people’s voices.{" "}
            <Citations numbers={[1]} />
          </p>
          <p>
            An accessible pronunciation resource can present regular spelling first, with a separate line for a researcher’s transcription when useful. It can provide clear audio and give listeners enough context to know whether the recording is a word, a sentence, or a stretch of conversation. In a text connected to an older source, it can retain the spelling of that edition and offer a searchable form alongside it. Readers then have a way to move between Zopau as they hear it and Zolai as they encounter it on the page. Henderson and Otsuka offer detailed starting points for readers interested in the analysis behind such a resource.{" "}
            <Citations numbers={[1, 16]} />
          </p>
        </section>

        <section id="grammar" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Grammar in speech and writing</h2>
          <p>
            Otsuka describes Tedim Chin as a language in which the predicate usually comes at the end of an unmarked clause. With an intransitive verb, an ordinary pattern places the subject before the verb. In a transitive clause, the actor and object can precede the verb. These descriptions refer to the organization of an ordinary clause. In a conversation, a participant may already be understood from the preceding lines, and longer passages offer more context than an isolated sentence. A learner can begin with ordinary clause order and then observe how it appears in dialogue and narrative.{" "}
            <Citations numbers={[1]} />
          </p>
          <p>
            One feature that receives sustained attention in the literature is verb stem alternation. Many verbs have two forms, commonly called Form I and Form II. The forms occur in different grammatical settings. Otsuka examines the pattern in colloquial speech and shows why a single rule of thumb cannot cover all the cases discussed in the grammatical literature. A vocabulary entry that gives both forms and links each to an attested example provides more information than a short English gloss alone. Seeing the wider sentence can help the learner understand why that form occurred there.{" "}
            <Citations numbers={[1, 15, 16]} />
          </p>
          <p>
            A careful reader also pays attention to small grammatical forms surrounding the verb and the noun phrase. Linguists describe some of these forms as clitics because of their relationship to adjacent material. A full analysis may use a separate line of glosses to show what a marker does, followed by a translation that reads naturally in English. The gloss and the translation serve different readers. The first helps explain the structure of the source sentence, and the second conveys the meaning of the complete passage. Otsuka’s grammatical sketch includes examples with this kind of detail.{" "}
            <Citations numbers={[1]} />
          </p>
          <p>
            Otsuka’s study of the form written as -sàk examines causative and benefactive constructions in colloquial Tedim Chin. A causative construction concerns bringing about an action or event. A benefactive construction brings in a participant for whose benefit something is done. This study shows the value of looking at a grammatical form across a set of sentences. Its role becomes clearer when the reader can compare the people involved, what happens to them, and how the whole clause is constructed. It is an example of the kind of question a reference grammar can address in more depth than a word list.{" "}
            <Citations numbers={[15]} />
          </p>
          <p>
            Written and colloquial sources can reveal different patterns. Henderson’s book analyzes two texts, while Otsuka’s research includes material collected in Yangon and Kalay. A reader comparing them can pay attention to how each author gathered the examples and describes the style under study. A dictionary editor can preserve those distinctions by identifying an example as a recorded conversation, published prose, or a particular literary source. For learners, this gives a clearer picture of when a form is likely to be heard or read.{" "}
            <Citations numbers={[1, 15, 16]} />
          </p>
        </section>

        <section id="grammar-examples" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Reading examples in a grammar</h2>
          <p>
            Otsuka’s study of causatives and benefactives gives a small set of forms that illustrate what can change between the two stems of a verb. In his transcription, the verb meaning “to go” has the forms pai and pài. The letters stay the same and the tone marking changes. The verb meaning “to call” appears as sám and sàp, where the final consonant changes as well as the tone marking. In the pair néː and néːk, meaning “to eat,” the second form ends in a consonant. The mark ː indicates vowel length in this transcription. These examples come from the study’s table of stem alternations.{" "}
            <Citations numbers={[15]} />
          </p>
          <p>
            A table like this answers a question about the shape of the forms. A sentence answers a different question about why a speaker chose a particular form. When comparing examples, begin by finding the verb and identifying the other participants. Then check whether the line is a complete utterance or a part of a longer sentence. Finally, compare the author’s word-by-word analysis with the English translation. If two examples have the same English translation, their surrounding clauses can still reveal a grammatical difference. This is one reason a useful grammar gives both a compact table and examples in context.{" "}
            <Citations numbers={[1, 15]} />
          </p>
          <p>
            The same study gives hòiʔ for both stems of a verb meaning “to be good.” The symbol ʔ represents a glottal stop. Here the distinction between the two forms depends on grammatical analysis because the recorded forms sound alike. It is useful to keep that example beside the more visible alternations. A dictionary interface may have separate fields for the two forms while showing the same spelling in each field when the evidence calls for it. Readers can then see which features are documented and how the entry relates to examples.{" "}
            <Citations numbers={[15]} />
          </p>
          <p>
            These examples are written in a linguist’s transcription. Readers may encounter familiar spellings in ordinary Zolai publications that do not include the same pronunciation marks. A reading edition can show the words as they appear in the publication and link separately to a pronunciation note. For someone learning through family speech, an audio recording can supply another point of comparison. Keeping the original publication, transcription, and recording identifiable makes it possible to compare how the forms appear in each source and to ask a speaker about the usage they recognize.
          </p>
        </section>

        <section id="latin-script" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">The Latin writing tradition</h2>
          <p>
            The Latin-based writing system used in Tedim Chin is associated with Joseph Herbert Cope, whose work Otsuka places in the early twentieth century. The spread of that orthography belongs to a wider history of schooling, publishing, translation, and religious activity in the Chin Hills. A history of education hosted by the University of Bologna describes the establishment of the mission center in Tedim and the production of school texts. Read alongside Otsuka’s account of the orthography, it provides context for how written materials entered classrooms and other institutions.{" "}
            <Citations numbers={[1, 15, 17]} />
          </p>
          <p>
            A community bibliography published by Zomi Daily lists works associated with Cope, including readers and scripture publications. This list is a starting point for examining Zolai print history. It names works that a reader can then look for in libraries, missionary archives, personal collections, or original scans. Bibliographic details matter when old texts carry a spelling different from that used today. A title page may record a particular edition, publisher, or language label. An archive entry can preserve that information alongside a more familiar modern search title.{" "}
            <Citations numbers={[18]} />
          </p>
          <p>
            Historical writing also includes examples outside books intended for formal study. Khoi Lam Thang discusses a Tedim monthly publication, Tedim Kam Thu Kizakna, and places its beginning in 1919. A periodical offers a different view of writing from a grammar or school reader. Its issues can show how editors wrote about events for recurring readers. To study a specific issue, the best evidence is the issue itself, with its date, pages, and publisher recorded. A scholarly mention can point toward an item even when the surviving copies are difficult to locate.{" "}
            <Citations numbers={[25]} />
          </p>
          <p>
            Changes in printing and editing can affect spelling across editions. An editor may preserve a historical spelling when transcribing a page and supply another form to help present-day readers search for it. Both can be useful if the edition identifies which one comes from the source. When a printed text is hard to read, the page image lets readers compare the transcription with the original. A transcription that marks an uncertain word gives a later reviewer a clear place to check. These choices make a digital edition useful to learners and researchers who ask different questions of the same document.
          </p>
          <p>
            The Latin script also makes Zolai accessible through familiar digital tools such as keyboards, browsers, and search. A learner may still need guidance on the relation between spelling and pronunciation. A plain-text edition can preserve the published spelling, and the accompanying audio can demonstrate how the passage is read by a named speaker or contributor. A digitized work can then support both literary reading and spoken-language practice. That connection is particularly useful when a text originally reached its audience through public reading, teaching, or song.
          </p>
          <p>
            Khoi Lam Thang also places the start of vernacular education in Tedim, Falam, Hakha, and Chinbok in 1925. His account situates early Tedim publications alongside the literacy histories of other Chin communities. That comparison helps explain why the language of a reader or periodical matters as much as the place it was printed. In a catalog of school materials, identifying the language of instruction and the language printed on the page can reveal how a book was meant to be used. A historical account of several communities also gives readers a way to see which dates refer specifically to Tedim and which describe a wider initiative.{" "}
            <Citations numbers={[25]} />
          </p>
        </section>

        <section id="pau-cin-hau" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Pau Cin Hau and the Laipian tradition</h2>
          <p>
            The history of writing Tedim also includes the scripts developed by Pau Cin Hau, who lived from 1859 to 1948 and founded the Laipian religious tradition. The Unicode Standard describes the Pau Cin Hau alphabet as a liturgical script that emerged in the Chin Hills. It was designed to represent Tedim, and the standard notes characters for sounds that occur in other Chin languages as well. This history gives readers another example of how writing can develop in close connection with a community’s teaching and religious life.{" "}
            <Citations numbers={[7]} />
          </p>
          <p>
            Anshuman Pandey’s technical work describes two different forms of the script tradition. One is the earlier system he discusses in his paper on logographs. The other is the later alphabet that his encoding proposal presents. The two documents show different inventories and organizing principles. Calling both simply Pau Cin Hau writing can be convenient in general conversation. In a catalog or a discussion of a particular page, specifying the system makes it possible to find the right scholarly description and understand how the signs are being interpreted.{" "}
            <Citations numbers={[19, 20]} />
          </p>
          <p>
            The Pau Cin Hau alphabet entered Unicode in version 7.0. Its block runs from U+11AC0 through U+11AFF. Unicode defines code points that let software represent the same characters consistently. A font and rendering environment are still needed to show the shapes. For a reader interested in viewing an older manuscript, a photograph or scan can supply additional information about handwriting, spacing, and physical layout. For a reader who wants to search or copy a passage in the alphabet, a verified digital transcription offers a different kind of access.{" "}
            <Citations numbers={[7, 19]} />
          </p>
          <p>
            Pandey’s study of the earlier system includes illustrations of documentary evidence, including a stone inscription. A historical object can answer questions about how characters were used in a particular place or material. Its transcription may also reflect the analyst’s decisions about a damaged or unfamiliar sign. A reference to the object and a link to the technical paper make it possible to follow those decisions. They can also help a reader identify the correct writing system before relying on an electronic font or character chart.{" "}
            <Citations numbers={[20]} />
          </p>
          <p>
            Pau Cin Hau writing belongs within a history of Zolai because it records a community’s use of written Tedim. A reader can approach it as a writing system, a form of religious expression, or a body of historical documents. Each approach benefits from naming the particular object, publication, or community practice under discussion. The Unicode chapter is a useful entry point for the alphabet. Pandey’s separate treatment of the earlier signs supplies a starting point for the other system and its surviving examples.{" "}
            <Citations numbers={[7, 19, 20]} />
          </p>
        </section>

        <section id="literature" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Zolai literature and translation</h2>
          <p>
            Zolai includes writing that people read, study, adapt, and share. The historical record visible in the sources for this article includes school readers, periodical writing, and religious publications. These materials were produced for different purposes. A school reader organizes text for instruction. A periodical has dates and recurring issues. A translation relates to a source text and may have several versions intended for different readers. A literary archive can make these differences visible in its catalog, giving readers enough context to choose a work and understand the edition they opened.{" "}
            <Citations numbers={[17, 18, 25]} />
          </p>
          <p>
            Bible translation is one well-documented part of Zolai publication history. The Digital Bible Society catalogs a Tedim Bible and a separate 2011 Tedim Chim Bible. Its records identify the language, publisher, and links to reading or listening services. They also describe the work of Kam Khaw Thang and a committee of the Tiddim Baptist Association in the history of these editions. Naming a specific title and edition helps readers distinguish the work of a translator or committee from that of later publishers and editors.{" "}
            <Citations numbers={[21, 22]} />
          </p>
          <p>
            Historical dates in translation bibliographies can differ because bibliographies track different milestones. A partial translation can appear before a full New Testament. A complete Bible can be followed by a reference edition or a revised publication. Khoi Lam Thang’s historical discussion and the Digital Bible Society’s edition records can be read together with these distinctions in mind. A dated title page or publisher’s record can anchor a claim about a specific edition. A table in a secondary source is useful for seeing the wider sequence and finding names to investigate.{" "}
            <Citations numbers={[21, 22, 25]} />
          </p>
          <p>
            A text can also cross the boundary between oral performance and writing. Someone may learn a hymn by ear before seeing the printed words. A story can be recorded as told, then edited for a school reader. A translation can appear in a reading edition and an audio edition. The recording may preserve performance choices such as pace, emphasis, or phrasing. The written version makes it easier to find a passage, compare wording, and read it again at a different pace. A resource that has both versions can identify how they relate and which edition was used for the recording.
          </p>
          <p>
            The writing available online represents a part of the tradition that can be documented and accessed digitally. Families and local institutions may hold books, periodicals, handwritten pieces, and recorded performances with their own histories. For future additions to a literary reference, useful details include title, author or collector, community or place, approximate date, edition, and the location of an accessible copy. Where an item was passed down orally, identifying the teller and recording context can be as valuable as identifying a publisher for a printed work. The record can make the work easier to find and credit the people who preserved it.
          </p>
        </section>

        <section id="education" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Education and public life</h2>
          <p>
            Language education can mean learning to read and write one’s home language, receiving instruction in that language, or studying it alongside another language used at school. Each use places different demands on a curriculum. A class learning to read can start with familiar spoken words and build toward extended texts. Subject teaching also needs ways to discuss concepts in fields such as science or mathematics. A curriculum project can document how terms were selected, which examples were tried with students, and what revisions teachers made. These details are particularly valuable when a curriculum is shared between communities.{" "}
            <Citations numbers={[23, 24]} />
          </p>
          <p>
            The Zomi Education Working Group describes its own work in education and preservation. Its 2021–22 report documents activities such as developing video lessons, distributing home-based learning materials, and supporting learning centers. Its curriculum development page describes the challenge of expanding available terminology and strengthening locally relevant content. The report provides a dated account of activities by the organization. Its curriculum page gives readers the group’s explanation of why it is working on learning materials and where it sees room to develop them.{" "}
            <Citations numbers={[4, 8, 24]} />
          </p>
          <p>
            A broader report on language and education in Chin State describes local curriculum arrangements and refers to Tedim Zomi Chin among the communities with local-language media. The policy report and the education group’s publications have different viewpoints. The first describes institutional conditions across the state. The second describes work undertaken by a particular organization. A reader trying to understand how language education operates in one school or township may need a dated local curriculum or direct evidence from that school to add detail.{" "}
            <Citations numbers={[8, 23, 24]} />
          </p>
          <p>
            Tulsa provides examples of how Zopau enters public services outside Myanmar. A city briefing describes the Sia Mah Nu peer education program, including bilingual educators providing health information in Zopau or Zomi. The Tulsa Health Department’s interpreter job description identifies translation and interpretation duties involving Zomi. A city adult English-language needs assessment lists Zomi in a table of Tulsa Public Schools language data. Together these documents show how a language can appear in programs involving health, education, and access to public information.{" "}
            <Citations numbers={[5, 10, 11, 26]} />
          </p>
          <p>
            These local records are most informative when their original purposes are kept in view. A job description describes a service and its duties. A briefing explains a program. A school language table reflects the students and reporting methods that produced that table. A household might use several languages depending on who is talking and what they are doing. For someone writing about language use in Tulsa, pairing administrative records with an attributed interview or community publication can add detail about use at home, in worship, and in community gatherings.
          </p>
          <p>
            The City of Tulsa’s Asian Affairs Commission presentation uses the name Zopau when discussing speakers in Tulsa’s Myanmar-origin community. The peer education briefing uses the paired names Zopau and Zomi for the language of its instruction. These records give readers a practical example of the names used for public communication. Someone looking for written materials can use the spelling a public agency used in its catalog, and someone documenting the language of a spoken presentation can record the name used by its presenters.{" "}
            <Citations numbers={[5, 10]} />
          </p>
        </section>

        <section id="using-references" className="scroll-mt-24 space-y-4">
          <h2 className="font-playfair text-2xl font-semibold">Using the references and building a record</h2>
          <p>
            A useful way to explore Zopau and Zolai is to begin with the question being asked and choose a source that was made to answer it. Otsuka’s sketch is an entry point for spoken grammar and geographical context. Henderson offers a historical descriptive study organized around texts. Glottolog supplies a language identifier and links to classifications and references. A publisher’s or catalog’s edition record gives details about a printed or digital work. A community organization describes its programs and the language needs it encounters. Reading each source for its particular evidence makes it easier to compare accounts.{" "}
            <Citations numbers={[1, 2, 4, 16, 21]} />
          </p>
          <p>
            Readers interested in pronunciation can begin with a short passage that has a recording. Listening first gives a sense of the rhythm of the complete sentence. Following the written line helps locate words that were hard to hear. Checking a grammar can then explain a tone change or a verb form that stood out. A learner interested in Zolai can work in the other direction by reading a short passage first and then listening to a speaker’s reading of the same text. Both methods work best when the text and recording are clearly identified and can be revisited.
          </p>
          <p>
            For a historical claim, titles, dates, and page numbers make the evidence easier to check. A citation to a grammar can identify the section about tone or word order. A claim about a book can cite its edition and publisher. A claim about the location of an educational project can cite the organization’s dated report. When two sources use different terms, a short explanation of their usage gives readers the information needed to compare them. For an old scan, a stable record for the scan and the page number inside the original work can both be useful.
          </p>
          <p>
            A digital archive can also preserve several levels of detail for the same item. At the catalog level, a reader might see its language, title, date, and genre. Opening the record can reveal the creator, place of publication, edition, and where the copy came from. A paired transcription and scan allows closer study. An attached recording can document pronunciation or performance. Including the source and edition in a citation makes it possible for another reader to identify the same version, even if the web address changes over time.
          </p>
          <p>
            Siamsil’s dictionary, lessons, Bible reader, and library offer starting points for exploring the language. The dictionary is useful for finding a word and examining its forms in context. Lessons can connect the written language with the language a learner hears. The library offers a place to look for works and references, and the Bible reader makes it possible to locate passages by book and verse. As a shared reference point for these activities, this article records the names and terminology that help readers move between community usage, linguistic research, and published Zolai. The references below provide the next level of detail for readers who want to follow a specific topic.
          </p>
        </section>

        <section id="references" className="scroll-mt-24 space-y-3">
          <h2 className="font-playfair text-2xl font-semibold">References</h2>
          <ol className="list-decimal space-y-2 pl-6">
            <li id="source-1" className="scroll-mt-24">
              <a className="underline" href="https://hdl.handle.net/10108/88511">Kosei Otsuka (2014). “Tiddim Chin.” Grammatical Sketches from the Field, vol. 2, pp. 109–141.</a>
            </li>
            <li id="source-2" className="scroll-mt-24">
              <a className="underline" href="https://glottolog.org/resource/languoid/id/tedi1235">Glottolog. Tedim Chin (tedi1235).</a>
            </li>
            <li id="source-3" className="scroll-mt-24">
              <a className="underline" href="https://arc.dbs.org/data/languages/ctd/">Digital Bible Society. Tedim Chin language catalog.</a>
            </li>
            <li id="source-4" className="scroll-mt-24">
              <a className="underline" href="https://zomieducation.org/">Zomi Education Working Group. About us and the Zomi context in Myanmar.</a>
            </li>
            <li id="source-5" className="scroll-mt-24">
              <a className="underline" href="https://istulsa.org/shared/asianaffairspresentation.pdf">City of Tulsa Asian Affairs Commission. Presentation on Tulsa’s Asian communities.</a>
            </li>
            <li id="source-6" className="scroll-mt-24">
              <a className="underline" href="https://glottolog.org/resource/reference/id/154366">Christopher T. J. Button (2009). A Reconstruction of Proto Northern Chin in Old Burmese and Old Chinese Perspective. Glottolog bibliographic record.</a>
            </li>
            <li id="source-7" className="scroll-mt-24">
              <a className="underline" href="https://unicode.org/versions/Unicode17.0.0/core-spec/chapter-16/">Unicode Consortium. The Unicode Standard, chapter 16, section 16.13, Pau Cin Hau.</a>
            </li>
            <li id="source-8" className="scroll-mt-24">
              <a className="underline" href="https://zomieducation.org/wp-content/uploads/2022/06/annual-report.zewg_.2021_22.17june2022.pdf">Zomi Education Working Group (2022). Annual report 2021–22.</a>
            </li>
            <li id="source-9" className="scroll-mt-24">
              <a className="underline" href="https://myanmar.unfpa.org/sites/default/files/resource-pdf/Chin_Tedim_en.pdf">Myanmar Department of Population. 2014 Myanmar Population and Housing Census, Tedim Township Report.</a>
            </li>
            <li id="source-10" className="scroll-mt-24">
              <a className="underline" href="https://www.cityoftulsa.org/media/18181/tulsa-rfp-funds-briefing-book-3-11-22.pdf">City of Tulsa. Coronavirus relief funding briefing, Sia Mah Nu program.</a>
            </li>
            <li id="source-11" className="scroll-mt-24">
              <a className="underline" href="https://www.cityoftulsa.org/media/27604/leap-city-of-tulsa_-george-kaiser-family-foundation_-tulsa-community-college-adult-esl-needs-assessment-report.pdf">City of Tulsa and partners. Adult ESL Needs Assessment Report, figure 6.</a>
            </li>
            <li id="source-12" className="scroll-mt-24">
              <a className="underline" href="https://stedt.berkeley.edu/pubs_and_prods/STEDT_Monograph8_Proto-Kuki-Chin.pdf">Kenneth VanBik (2009). Proto-Kuki-Chin: A Reconstructed Ancestor of the Kuki-Chin Languages.</a>
            </li>
            <li id="source-13" className="scroll-mt-24">
              <a className="underline" href="https://glottolog.org/resource/languoid/id/pait1244">Glottolog. Paite Chin (pait1244).</a>
            </li>
            <li id="source-14" className="scroll-mt-24">
              <a className="underline" href="https://glottolog.org/resource/languoid/id/zouu1235">Glottolog. Zou (zouu1235).</a>
            </li>
            <li id="source-15" className="scroll-mt-24">
              <a className="underline" href="https://www.tufs.ac.jp/ts/personal/kazama/shigen/5/Otsuka.pdf">Kosei Otsuka (2009). “Causative and benefactive suffix -sàk in Tiddim Chin.” See section 2 and table 1.</a>
            </li>
            <li id="source-16" className="scroll-mt-24">
              <a className="underline" href="https://books.google.com/books?id=1UjDAQAACAAJ">Eugénie J. A. Henderson (1965). Tiddim Chin: A Descriptive Analysis of Two Texts. Oxford University Press.</a>
            </li>
            <li id="source-17" className="scroll-mt-24">
              <a className="underline" href="https://site.unibo.it/chinlone/it/results/ebook/ebook-final.pdf/@@download/file/EBOOK%20FINAL.pdf">Min Thang (2021). “The Introduction of Modern Education to Myanmar: an Ethnic Christian Perspective.” In Navigating the Evolution of Myanmar Higher Education, pp. 13–36.</a>
            </li>
            <li id="source-18" className="scroll-mt-24">
              <a className="underline" href="https://zomidaily.com/j-h-cope-laibu-bawlte-zolai/">Zomi Daily (2015). “J.H. Cope Laibu bawlte: Zolai.”</a>
            </li>
            <li id="source-19" className="scroll-mt-24">
              <a className="underline" href="https://escholarship.org/uc/item/43n28994">Anshuman Pandey (2011). Proposal to Encode the Pau Cin Hau Alphabet in ISO/IEC 10646.</a>
            </li>
            <li id="source-20" className="scroll-mt-24">
              <a className="underline" href="https://www.unicode.org/L2/L2010/10438-paucinhau-logographs.pdf">Anshuman Pandey (2010). Introducing the Logographic Script of Pau Cin Hau.</a>
            </li>
            <li id="source-21" className="scroll-mt-24">
              <a className="underline" href="https://arc.dbs.org/data/scripture/CTDTDB/index.html">Digital Bible Society. Tedim Bible (TDB), edition record.</a>
            </li>
            <li id="source-22" className="scroll-mt-24">
              <a className="underline" href="https://arc.dbs.org/data/scripture/CTDCLB/index.html">Digital Bible Society. Tedim Chim Bible (2011), edition record.</a>
            </li>
            <li id="source-23" className="scroll-mt-24">
              <a className="underline" href="https://covenant-consult.com/wp-content/uploads/Language-and-Education-in-Chin-State_Jan21.pdf">Ashley South et al. (2021). Language and Education in Chin State. Myanmar Education Partnerships Project working paper 1.</a>
            </li>
            <li id="source-24" className="scroll-mt-24">
              <a className="underline" href="https://zomieducation.org/curriculum-development/">Zomi Education Working Group. Curriculum Development.</a>
            </li>
            <li id="source-25" className="scroll-mt-24">
              <a className="underline" href="https://citeseerx.ist.psu.edu/document?doi=b94f1a7435efec3303e9826d8546046a5e80314a&amp;repid=rep1&amp;type=pdf">Khoi Lam Thang (2001). A Phonological Reconstruction of Proto Chin. Payap University, pp. 29–30.</a>
            </li>
            <li id="source-26" className="scroll-mt-24">
              <a className="underline" href="https://www.tulsa-health.org/sites/default/files/2020-06/7007%20Interpreter%20Temp-Part-time%20Burmese-Zomi.pdf">Tulsa Health Department. Burmese/Zomi interpreter job description.</a>
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
