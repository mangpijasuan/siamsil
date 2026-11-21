import type { Metadata } from "next";
import Link from "next/link";
import "../services/services.css";

export const metadata: Metadata = {
  title: "Products",
  description: "Explore Siamsil's Zomi dictionary, translation, Bible, learning, library, AI tools, and future applications.",
  alternates: { canonical: "/products" },
};

const available = [
  { name: "Dictionary", detail: "Search English and Zomi words, with source and verification labels.", href: "/zomidictionary" },
  { name: "Translate", detail: "Find stored translation pairs; unverified content is identified.", href: "/zomitranslate" },
  { name: "Bible", detail: "Read and search permitted Zomi Bible editions.", href: "/bible" },
  { name: "Library", detail: "Explore books and cultural resources.", href: "/library" },
  { name: "Learn", detail: "Study phrases and learning materials.", href: "/learning" },
  { name: "Siamsil AI", detail: "Explore source-grounded language assistance.", href: "/chat" },
];
const planned = [
  { name: "iOS & Android", detail: "Native-feeling mobile apps for Siamsil language tools." },
  { name: "Review Center", detail: "Secure editorial verification workspace, currently in development." },
  { name: "Church Management", detail: "Community-oriented membership and administration workflows under development." },
];
export default function ProductsPage() {
  return <div className="svc-page">
    <header className="svc-hero">
      <p className="svc-eyebrow">SIAMSIL · PRODUCTS</p>
      <h1>Language, knowledge, and intelligent tools.</h1>
      <p>Discover the Siamsil experiences you can use today and the applications we are developing for the future.</p>
      <div className="svc-actions"><Link className="svc-primary" href="/zomidictionary">Open Dictionary</Link><Link className="svc-secondary" href="/services">Explore services</Link></div>
    </header>
    <main className="svc-content">
      <div className="svc-section-head"><p className="svc-eyebrow">AVAILABLE EXPERIENCES</p><h2>Explore Siamsil</h2></div>
      <div className="svc-grid">{available.map((item) => <Link className="svc-card svc-product" href={item.href} key={item.name}><span className="svc-tag">Explore</span><h3>{item.name}</h3><p>{item.detail}</p><span className="svc-link">Open product →</span></Link>)}</div>
      <div className="svc-section-head svc-later"><p className="svc-eyebrow">ROADMAP</p><h2>In development or planned</h2><p>These are not advertised as released products.</p></div>
      <div className="svc-grid">{planned.map((item) => <article className="svc-card" key={item.name}><span className="svc-tag">Not released</span><h3>{item.name}</h3><p>{item.detail}</p></article>)}</div>
    </main>
  </div>;
}
