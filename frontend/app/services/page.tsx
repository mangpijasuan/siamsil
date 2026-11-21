import type { Metadata } from "next";
import Link from "next/link";
import "./services.css";

export const metadata: Metadata = {
  title: "Technology Services",
  description: "Explore Siamsil web development, mobile applications, AI integration, and community software services.",
  alternates: { canonical: "/services" },
};

const services = [
  { title: "Website Design & Development", description: "Accessible, responsive websites for organizations, churches, and businesses.", examples: "Corporate sites · Nonprofits · Church websites" },
  { title: "Custom Web Applications", description: "Purpose-built dashboards, management systems, and operational workflows.", examples: "Member portals · Reporting · Administration" },
  { title: "Mobile App Development", description: "iOS and Android application design and development using shared backend services.", examples: "Mobile experiences · Account integration · Notifications" },
  { title: "AI & Automation", description: "Practical AI-assisted workflows with appropriate human oversight, privacy, and cost controls.", examples: "Document workflows · Search · Assisted review" },
  { title: "Church & Community Technology", description: "Digital tools for membership, communication, events, and accountable donation records.", examples: "Church management · Giving · Events" },
  { title: "Maintenance & Modernization", description: "Improve existing websites and software through accessibility, security, and performance work.", examples: "Upgrades · Hosting guidance · Ongoing support" },
];

export default function ServicesPage() {
  return <div className="svc-page">
    <header className="svc-hero">
      <p className="svc-eyebrow">SIAMSIL TECHNOLOGIES · SERVICES</p>
      <h1>Technology built around your mission.</h1>
      <p>From a modern website to a connected application, Siamsil explores practical digital solutions for businesses, churches, and communities.</p>
      <div className="svc-actions"><Link href="/products" className="svc-primary">Explore products</Link><Link href="/about" className="svc-secondary">About Siamsil</Link></div>
    </header>
    <main className="svc-content">
      <div className="svc-section-head"><p className="svc-eyebrow">WHAT WE CAN BUILD</p><h2>Services & solutions</h2><p>These are service areas, not claims of completed client engagements or guaranteed availability.</p></div>
      <div className="svc-grid">{services.map((service, index) => <article className="svc-card" key={service.title}>
        <span className="svc-number">{String(index + 1).padStart(2, "0")}</span>
        <h3>{service.title}</h3><p>{service.description}</p><small>{service.examples}</small>
      </article>)}</div>
      <section className="svc-feature"><div><p className="svc-eyebrow">ONE CONNECTED ECOSYSTEM</p><h2>Services supported by products</h2><p>Our Zomi language tools, learning resources, and community applications inform how we design software. Explore what exists today and what is planned next.</p></div><Link href="/products" className="svc-primary">View Siamsil products</Link></section>
      <section className="svc-end"><h2>Have a project in mind?</h2><p>Explore our approach and project background. A public project intake form and service booking workflow are not yet available.</p><Link href="/about">Learn about Siamsil →</Link></section>
    </main>
  </div>;
}
