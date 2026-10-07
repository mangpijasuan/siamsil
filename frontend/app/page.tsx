import Link from "next/link";
import { IconArrow, IconBook, IconCross, IconAcademic, IconTranslate, IconChat } from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";

function formatCount(value?: number) {
  if (!value) return "—";
  return value.toLocaleString();
}

export default async function Home() {
  let verse = null;
  let word = null;
  let dictionaryCount = 0;
  let parallelCount = 0;
  let bibleCount = 0;

  try {
    const health = await getHealth();
    const language = health.language as Record<string, number> | null | undefined;
    dictionaryCount = language?.dictionary_entries ?? 0;
    parallelCount = language?.parallel_sentences ?? 0;
    const counts = health.metadata?.counts as Record<string, number> | undefined;
    bibleCount = counts?.bible_verses ?? 0;
  } catch {
    /* health is optional for first paint */
  }
  try { verse = await getDailyVerse(); } catch {}
  try { word = await getWordOfDay(); } catch {}

  return (
    <>
      <div className="home-hero">
        <div className="home-hero-label">Nisim Thalakna · Daily Verse</div>
      </div>

      <div style={{ padding: "0 16px", marginTop: -24, marginBottom: 4 }}>
        <div style={{
          background: "var(--white)",
          borderRadius: "var(--radius-lg)",
          padding: "20px 20px 20px 18px",
          boxShadow: "var(--shadow-lg)",
          borderLeft: "3px solid var(--gold)",
          display: "flex",
          alignItems: "flex-start",
          gap: 12,
        }}>
          <div className="font-playfair" style={{
            fontSize: 52, lineHeight: 0.7, color: "var(--gold)",
            opacity: 0.55, flexShrink: 0, marginTop: 6, userSelect: "none",
          }}>&ldquo;</div>
          <div style={{ flex: 1 }}>
            {verse ? (
              <>
                <p className="font-playfair" style={{
                  fontSize: 13.5, fontStyle: "italic", color: "var(--navy)",
                  lineHeight: 1.7, margin: "0 0 10px",
                }}>
                  {verse.zomi_iso}
                </p>
                <p style={{ fontSize: 10, color: "var(--gray)", fontWeight: 600, letterSpacing: "0.05em" }}>
                  — {verse.reference}
                </p>
              </>
            ) : (
              <p style={{ fontSize: 13, color: "var(--gray)", margin: 0 }}>
                Daily verse will appear when the API is running.
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="home-stats-row">
        <div className="home-stat">
          <span className="home-stat-num font-playfair">{formatCount(dictionaryCount)}</span>
          <span className="home-stat-label">Dictionary</span>
        </div>
        <div className="home-stat-div" />
        <div className="home-stat">
          <span className="home-stat-num font-playfair">{formatCount(parallelCount)}</span>
          <span className="home-stat-label">Sentence pairs</span>
        </div>
        <div className="home-stat-div" />
        <div className="home-stat">
          <span className="home-stat-num font-playfair">{formatCount(bibleCount)}</span>
          <span className="home-stat-label">Bible verses</span>
        </div>
      </div>

      <div className="section-header" style={{ paddingTop: 28 }}>
        <span className="section-title">Explore</span>
      </div>

      <div className="home-feat-grid">
        <Link href="/zomidictionary" className="hfeat-card hfeat-card--a" style={{ textDecoration: "none" }}>
          <div className="hfeat-icon"><IconBook size={22} /></div>
          <div className="hfeat-body">
            <div className="hfeat-title font-playfair">Dictionary</div>
            <div className="hfeat-sub">English headwords with Zomi definitions</div>
          </div>
          <div className="hfeat-arrow"><IconArrow size={12} /></div>
        </Link>

        <Link href="/bible" className="hfeat-card hfeat-card--b" style={{ textDecoration: "none" }}>
          <div className="hfeat-icon"><IconCross size={22} /></div>
          <div className="hfeat-body">
            <div className="hfeat-title font-playfair">Bible</div>
            <div className="hfeat-sub">Laisiangtho · 66 Books</div>
          </div>
          <div className="hfeat-arrow"><IconArrow size={12} /></div>
        </Link>

        <Link href="/learning" className="hfeat-card hfeat-card--c" style={{ textDecoration: "none" }}>
          <div className="hfeat-icon"><IconAcademic size={22} /></div>
          <div className="hfeat-body">
            <div className="hfeat-title font-playfair">Learning</div>
            <div className="hfeat-sub">Reviewed phrases only</div>
          </div>
          <div className="hfeat-arrow"><IconArrow size={12} /></div>
        </Link>

        <Link href="/zomitranslate" className="hfeat-card hfeat-card--d" style={{ textDecoration: "none" }}>
          <div className="hfeat-icon"><IconTranslate size={22} /></div>
          <div className="hfeat-body">
            <div className="hfeat-title font-playfair">Translate</div>
            <div className="hfeat-sub">Retrieve known pairs</div>
          </div>
          <div className="hfeat-arrow"><IconArrow size={12} /></div>
        </Link>
      </div>

      {word && (
        <div style={{ margin: "28px 16px 0" }}>
          <div className="section-header" style={{ padding: "0 0 14px" }}>
            <span className="section-title">Word of the Day</span>
            <Link href="/zomidictionary" style={{ textDecoration: "none" }}>
              <span className="section-link">Browse →</span>
            </Link>
          </div>

          <div className="wotd-card">
            <div className="wotd-card-accent" />
            <div className="wotd-card-body">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div className="gold-label" style={{ marginBottom: 8 }}>Thu Tawlbang</div>
                  <div className="font-playfair wotd-word">{word.english}</div>
                  {word.zomi && <div className="wotd-zomi">{word.zomi}</div>}
                </div>
                {word.part_of_speech && (
                  <span className="wotd-pos-badge">{word.part_of_speech}</span>
                )}
              </div>
              {word.definition && <p className="wotd-definition">{word.definition}</p>}
              <div className="wotd-actions">
                <Link
                  href={`/zomidictionary?q=${encodeURIComponent(word.english)}`}
                  className="wotd-btn wotd-btn--primary"
                >
                  Full Entry
                </Link>
                <Link href="/zomidictionary" className="wotd-btn wotd-btn--secondary">
                  Browse More
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ margin: "20px 16px 0" }}>
        <Link href="/bible" style={{ textDecoration: "none", display: "block" }}>
          <div className="reading-card">
            <div className="reading-card-icon">
              <IconCross size={18} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="reading-card-label">Read</div>
              <div className="reading-card-title">Zomi Holy Bible</div>
            </div>
            <span style={{ color: "var(--gold)", flexShrink: 0 }}><IconArrow size={16} /></span>
          </div>
        </Link>
      </div>

      <div style={{ margin: "14px 16px 0" }}>
        <Link href="/chat" style={{ textDecoration: "none", display: "block" }}>
          <div className="ai-promo-card">
            <div className="ai-promo-card-shimmer" />
            <div className="ai-promo-icon"><IconChat size={18} /></div>
            <div style={{ flex: 1 }}>
              <div className="ai-promo-label">Retrieval only · no generated Zomi</div>
              <div className="ai-promo-title">Ask Siamsil AI</div>
              <div className="ai-promo-sub">Answers from the dictionary, corpus, and Bible text</div>
            </div>
            <span style={{ color: "var(--gold)", flexShrink: 0 }}><IconArrow size={16} /></span>
          </div>
        </Link>
      </div>

      <div className="screen-pad" />
    </>
  );
}
