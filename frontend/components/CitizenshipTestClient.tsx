"use client";

import { useState } from "react";
import Link from "next/link";

type Question = {
  question: string;
  answers: string[];
  choices: string[];
  category: string;
  zomi: { question: string; answers: string[] };
  burmese: { question: string; answers: string[] };
};

const QUESTIONS: Question[] = [
  {
    question: "What is the supreme law of the land?",
    answers: ["The Constitution"],
    choices: ["The Constitution", "The Declaration of Independence", "The Bill of Rights", "Federal statutes"],
    category: "Principles of American Government",
    zomi: { question: "USA gam ii zuih thukhun Upadi thupi pen bang hiam?", answers: ["Gamki-ukna Thukhunpi hi"] },
    burmese: { question: "နိုင်ငံတော်၏ အမြင့်ဆုံးဥပဒေသည် ဘာလဲ?", answers: ["ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေ"] },
  },
  {
    question: "What does the Constitution do?",
    answers: ["Sets up the government", "Defines the government", "Protects basic rights of Americans"],
    choices: ["Sets up the government", "Elects the President", "Creates political parties", "Controls state elections"],
    category: "Principles of American Government",
    zomi: { question: "Gamki-ukna Thukhunpi in bangteng vaan hiam?", answers: ["Gam-uk ding kumpi phut", "Ki-ukzia ding geel", "Americans mite' septheih leh ngahtheih peuhmah peelhem saklo"] },
    burmese: { question: "ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေက ဘာတွေလုပ်သလဲ?", answers: ["အစိုးရကို ပုံဖော်ဖွဲ့စည်းပေးသည်", "အစိုးရ၏ တာဝန်တွေကို သတ်မှတ်သည်", "အမေရိကန်နိုင်ငံသားများ၏ အခြေခံအခွင့်အရေးတွေကို ကာကွယ်ပေးသည်"] },
  },
  {
    question: "The idea of self-government is in the first three words of the Constitution. What are these words?",
    answers: ["We the People"],
    choices: ["We the People", "Life and Liberty", "United We Stand", "In God We Trust"],
    category: "Principles of American Government",
    zomi: { question: "Gamki-ukna Thukhunpi sungah ei leh ei ki-ukzia ding lamlak kammal thumte bang hiam?", answers: ["Ei mipite"] },
    burmese: { question: "ကိုယ်ပိုင်အစိုးရထူထောင်ခြင်းဆိုင်ရာ အတွေးအခေါ်သည် ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေ၏ ပထမစကားလုံးသုံးလုံးတွင် ပါဝင်သည်။ ထိုစကားလုံးသုံးလုံးဟာ ဘာတွေလဲ?", answers: ["ငါတို့ အမေရိကန်ပြည်သူများ"] },
  },
  {
    question: "What is an amendment?",
    answers: ["A change to the Constitution", "An addition to the Constitution"],
    choices: ["A change to the Constitution", "A presidential election", "A court case", "A federal tax"],
    category: "Principles of American Government",
    zomi: { question: "Upadi Puahphatna/behlapna (Amendment) icih bang hiam?", answers: ["Akikheelna khat", "Guanbeh (Behlap)"] },
    burmese: { question: "ပြင်ဆင်ဖြည့်စွက်ချက်ဆိုသည်မှာ ဘာလဲ?", answers: ["ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေ၏ အစိတ်အပိုင်းတစ်ခုကို ပြင်ဆင်ခြင်း", "ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေကို ဖြည့်စွက်ခြင်း"] },
  },
  {
    question: "What do we call the first ten amendments to the Constitution?",
    answers: ["The Bill of Rights"],
    choices: ["The Bill of Rights", "The Declaration of Independence", "The Federalist Papers", "The Articles of Confederation"],
    category: "Rights and Responsibilities",
    zomi: { question: "Gamki-ukna Thukhunpi sungah Puahphat masakna sawmte bang kici hiam?", answers: ["Hamphatnading Upadi"] },
    burmese: { question: "ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေ၏ ပထမဆုံး ပြင်ဆင်ဖြည့်စွက်ချက် ၁၀ ခုကို ဘယ်လိုခေါ်သလဲ?", answers: ["လူတစ်ဦးချင်းစီ၏ အခြေခံအကျဆုံး အခွင့်အရေးများကို အာမခံထားသည့် ဥပဒေကြမ်း"] },
  },
  {
    question: "What is one right or freedom from the First Amendment?",
    answers: ["Speech", "Religion", "Assembly", "Press", "Petition the government"],
    choices: ["Speech", "Trial by jury", "Own a home", "Run for President"],
    category: "Rights and Responsibilities",
    zomi: { question: "Tua Puahphat Masakna ah hamphatna ahihkeh suahtakna khat bang ahia?", answers: ["Suaktataka thugentheihna", "Suaktataka Biakpiaktheihna", "Suaktataka Kikaihkhoptheihna", "Suaktataka Laigelh leh hawmtheihna", "Suaktataka Kumpi tungah lungkimlohna gentheih/pulaktheihna"] },
    burmese: { question: "ပထမဆုံး ပြင်ဆင်ဖြည့်စွက်ချက်မှ အခွင့်အရေးတစ်ခု သို့မဟုတ် လွတ်လပ်ခွင့်တစ်ခုကို ဖော်ပြပါ။", answers: ["လွတ်လပ်စွာ ပြောဆိုပိုင်ခွင့်", "လွတ်လပ်စွာ ကိုးကွယ်ပိုင်ခွင့်", "လွတ်လပ်စွာ စုဝေးပိုင်ခွင့်", "လွတ်လပ်စွာ ရေးသားထုတ်ဝေပိုင်ခွင့်", "အစိုးရထံသို့ လွတ်လပ်စွာ အယူခံတင်သွင်းပိုင်ခွင့်"] },
  },
  {
    question: "How many amendments does the Constitution have?",
    answers: ["Twenty-seven", "27"],
    choices: ["27", "10", "13", "50"],
    category: "Principles of American Government",
    zomi: { question: "Gamki-ukna Thukhunpi bangzah vei kipuahpha ta hiam?", answers: ["27 vei"] },
    burmese: { question: "ဖွဲ့စည်းအုပ်ချုပ်ပုံ အခြေခံဥပဒေတွင် ပြင်ဆင်ဖြည့်စွက်ချက် ဘယ်နှစ်ခုရှိပါသလဲ?", answers: ["နှစ်ဆယ့်ခုနှစ်ခု (၂၇)"] },
  },
  {
    question: "What did the Declaration of Independence do?",
    answers: ["Announced our independence from Great Britain", "Declared our independence from Great Britain", "Said that the United States is free from Great Britain"],
    choices: ["Declared our independence from Great Britain", "Ended the Civil War", "Created the Supreme Court", "Freed all enslaved people"],
    category: "American History",
    zomi: { question: "Suahtakna Thutangkopina bang hiam?", answers: ["Great Britain te kiangpan suahtak tangkona", "Great Britain te kiangpan suahtak pulakkhia", "United States suakta hi ei cihkhiatna"] },
    burmese: { question: "လွတ်လပ်ရေးကြေညာစာတမ်းက ဘာလုပ်ခဲ့သလဲ?", answers: ["ဗြိတိန်နိုင်ငံကြီး၏ လက်အောက်မှ လွတ်မြောက်ကြောင်း အသိပေးကြေညာသည်", "ဗြိတိန်နိုင်ငံကြီး၏ လက်အောက်မှ လွတ်မြောက်ကြောင်း အတည်ပြုကြေညာသည်", "အမေရိကန်နိုင်ငံ လွတ်လပ်ရေးရပြီဆိုတာကို ဖွင့်ဆိုပြောပြသည်"] },
  },
  {
    question: "What are two rights in the Declaration of Independence?",
    answers: ["Life", "Liberty", "Pursuit of happiness"],
    choices: ["Life", "Speech", "Vote", "Education"],
    category: "Rights and Responsibilities",
    zomi: { question: "Suahtakna Thutangkopi in hong phal hamphatna thunihte bang a hia?", answers: ["Nuntak khuasakna", "Kiphalna", "Nopsak banga zontheihna"] },
    burmese: { question: "လွတ်လပ်ရေးကြေညာစာတမ်းတွင်ပါသော အခွင့်အရေးနှစ်ခုသည် ဘာလဲ?", answers: ["အသက်ရှင်ရပ်တည်ခွင့်", "လွတ်လပ်ခွင့်", "ပျော်ရွှင်မှုရှာဖွေပိုင်ခွင့်"] },
  },
  {
    question: "What is freedom of religion?",
    answers: ["You can practice any religion, or not practice a religion"],
    choices: ["You can practice any religion, or not practice a religion", "The government chooses a religion", "Only citizens may worship", "Every state chooses a religion"],
    category: "Rights and Responsibilities",
    zomi: { question: "Biakna Suahtakna in bang hiam?", answers: ["Biakna khat peuhpeuh ah na utleh biathei/bialothei lel a omna"] },
    burmese: { question: "ဘာသာရေးလွတ်လပ်ခွင့်ဆိုတာ ဘာလဲ?", answers: ["မိမိယုံကြည်ရာ မည်သည့်ဘာသာကိုမဆို ကိုးကွယ်နိုင် သို့မဟုတ် မကိုးကွယ်ဘဲ နေနိုင်သည်"] },
  },
];

export default function CitizenshipTestClient() {
  const [language, setLanguage] = useState<"english" | "zomi" | "burmese">("english");
  const [mode, setMode] = useState<"study" | "practice">("study");
  const [current, setCurrent] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const question = QUESTIONS[current];
  const displayedQuestion = language === "english" ? question.question : question[language].question;
  const displayedAnswers = language === "english" ? question.answers : question[language].answers;
  const correct = selected ? question.answers.some((answer) => answer.toLowerCase() === selected.toLowerCase()) : false;

  function restart(nextMode = mode) {
    setMode(nextMode);
    setCurrent(0);
    setRevealed(false);
    setSelected(null);
    setScore(0);
    setFinished(false);
  }

  function nextQuestion() {
    if (current === QUESTIONS.length - 1) {
      setFinished(true);
      return;
    }
    setCurrent((value) => value + 1);
    setRevealed(false);
    setSelected(null);
  }

  function chooseAnswer(choice: string) {
    if (selected) return;
    setSelected(choice);
    if (question.answers.some((answer) => answer.toLowerCase() === choice.toLowerCase())) {
      setScore((value) => value + 1);
    }
  }

  return (
    <div className="citizenship-page">
      <header className="citizenship-hero">
        <div className="citizenship-hero-copy">
          <Link href="/learning" className="citizenship-back">← Learning</Link>
          <span className="citizenship-kicker">🇺🇸 Multilingual civics preview</span>
          <h1 className="font-playfair">U.S. Citizenship Test</h1>
          <p>Explore a 10-question preview in English, Zomi, and Burmese based on the supplied multilingual guide.</p>
        </div>
        <div className="citizenship-test-facts">
          <div><strong>{QUESTIONS.length}</strong><span>Questions included</span></div>
          <div><strong>3</strong><span>Study languages</span></div>
          <div><strong>100</strong><span>Questions in source guide</span></div>
        </div>
      </header>

      <main className="citizenship-content">
        <div className="citizenship-notice">
          <span aria-hidden="true">ℹ️</span>
          <p>The supplied ZAUS guide was published in 2013 and contains the older 100-question civics material. Siamsil currently includes only its first 10 questions. It is a study preview, not a complete or official test. USCIS now also publishes a 2025 version with 128 questions; confirm which version applies to your case and check answers that can change.</p>
          <a href="https://www.uscis.gov/citizenship/testupdates" target="_blank" rel="noopener noreferrer">Check USCIS updates ↗</a>
        </div>

        <div className="citizenship-mode-tabs" role="tablist" aria-label="Citizenship learning mode">
          <button type="button" className={mode === "study" ? "active" : ""} onClick={() => restart("study")}>Study cards</button>
          <button type="button" className={mode === "practice" ? "active" : ""} onClick={() => restart("practice")}>Practice test</button>
        </div>

        <div className="citizenship-language-tabs" role="group" aria-label="Study language">
          <span>Study language</span>
          <div>
            <button type="button" className={language === "english" ? "active" : ""} onClick={() => setLanguage("english")}>English</button>
            <button type="button" className={language === "zomi" ? "active" : ""} onClick={() => setLanguage("zomi")}>Zomi</button>
            <button type="button" className={language === "burmese" ? "active" : ""} onClick={() => setLanguage("burmese")}>မြန်မာ</button>
          </div>
          {mode === "practice" && language !== "english" && <p>Questions and answer review use {language === "zomi" ? "Zomi" : "Burmese"}; practice choices remain in English for oral-test preparation.</p>}
        </div>

        {finished ? (
          <section className="citizenship-result">
            <span className="citizenship-result-icon">{score >= 6 ? "🎉" : "📚"}</span>
            <span className="gold-label">Practice complete</span>
            <h2 className="font-playfair">{score} out of {QUESTIONS.length} correct</h2>
            <p>{score >= 6 ? "Good work. Keep reviewing until every answer feels natural when spoken aloud." : "Keep studying, then try again."} This preview score is not an official pass result; the real civics test is oral.</p>
            <button type="button" onClick={() => restart("practice")}>Try again</button>
          </section>
        ) : (
          <section className="citizenship-card">
            <div className="citizenship-card-top">
              <span>{question.category}</span>
              <span>{current + 1} / {QUESTIONS.length}</span>
            </div>
            <div className="citizenship-progress"><span style={{ width: `${((current + 1) / QUESTIONS.length) * 100}%` }} /></div>
            <h2 className={language === "burmese" ? "citizenship-burmese" : "font-playfair"}>{displayedQuestion}</h2>
            {language !== "english" && <p className="citizenship-english-reference">{question.question}</p>}

            {mode === "study" ? (
              <>
                <button type="button" className="citizenship-reveal" onClick={() => setRevealed(true)} disabled={revealed}>
                  {revealed ? "Answer revealed" : "Reveal answer"}
                </button>
                {revealed && (
                  <div className="citizenship-answer">
                    <span className="gold-label">Accepted answers include</span>
                    <ul>{displayedAnswers.map((answer) => <li key={answer}>{answer}</li>)}</ul>
                    {language !== "english" && <p className="citizenship-answer-english">English: {question.answers.join(" / ")}</p>}
                    <p>Practice saying one accepted answer aloud.</p>
                  </div>
                )}
              </>
            ) : (
              <div className="citizenship-choices">
                {question.choices.map((choice) => {
                  const isCorrectChoice = question.answers.some((answer) => answer.toLowerCase() === choice.toLowerCase());
                  const state = selected ? (isCorrectChoice ? "correct" : selected === choice ? "incorrect" : "") : "";
                  return <button key={choice} type="button" className={state} onClick={() => chooseAnswer(choice)}>{choice}</button>;
                })}
                {selected && <p className={correct ? "feedback-correct" : "feedback-incorrect"}>{correct ? "Correct" : `Review: ${displayedAnswers[0]}`}</p>}
              </div>
            )}

            <div className="citizenship-card-actions">
              <button type="button" onClick={() => { setCurrent((value) => Math.max(0, value - 1)); setRevealed(false); setSelected(null); }} disabled={mode === "practice" || current === 0}>Previous</button>
              <button type="button" className="primary" onClick={nextQuestion} disabled={mode === "study" ? !revealed : !selected}>
                {current === QUESTIONS.length - 1 ? "Finish" : "Next question"}
              </button>
            </div>
          </section>
        )}

        <div className="citizenship-official-links">
          <div>
            <span className="gold-label">Official study material</span>
            <h3 className="font-playfair">Open the current USCIS guide</h3>
            <p>Use USCIS material for the complete current question bank and rules. Siamsil’s multilingual module is an older-guide preview.</p>
          </div>
          <a href="https://www.uscis.gov/sites/default/files/document/questions-and-answers/2025-Civics-Test-128-Questions-and-Answers.pdf" target="_blank" rel="noopener noreferrer">Open 2025 USCIS guide ↗</a>
        </div>
      </main>
      <div className="screen-pad" />
    </div>
  );
}
