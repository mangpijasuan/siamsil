"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconAcademic,
  IconBook,
  IconChat,
  IconCross,
  IconHome,
  IconLibrary,
  IconSearch,
  IconTranslate,
  IconUser,
} from "./Icons";

export const NAV_TABS = [
  { href: "/", Icon: IconHome, label: "Home", hint: "Your Zomi library" },
  { href: "/library", Icon: IconLibrary, label: "Library", hint: "Books & archives" },
  { href: "/zomidictionary", Icon: IconBook, label: "Dictionary", hint: "Zomi–English" },
  { href: "/bible", Icon: IconCross, label: "Bible", hint: "Laisiangtho" },
  { href: "/learning", Icon: IconAcademic, label: "Learning", hint: "Grammar & phrases" },
  { href: "/zomitranslate", Icon: IconTranslate, label: "Translate", hint: "Retrieve known pairs" },
  { href: "/chat", Icon: IconChat, label: "Siamsil AI", hint: "Retrieval assistant" },
  { href: "/profile", Icon: IconUser, label: "Profile", hint: "Progress & settings" },
];

const PAGE_META = [
  { match: /^\/$/, eyebrow: "Zomi literature hub", title: "Home" },
  { match: /^\/learning\/citizenship/, eyebrow: "Learning · U.S. civics", title: "Citizenship test" },
  { match: /^\/library/, eyebrow: "Books & archives", title: "Library" },
  { match: /^\/zomidictionary/, eyebrow: "Words & meaning", title: "Dictionary" },
  { match: /^\/bible/, eyebrow: "Laisiangtho", title: "Bible" },
  { match: /^\/learning/, eyebrow: "Build your fluency", title: "Learning" },
  { match: /^\/zomitranslate/, eyebrow: "English ↔ Zomi", title: "Translate" },
  { match: /^\/chat/, eyebrow: "Zomi language assistant", title: "Siamsil AI" },
  { match: /^\/profile/, eyebrow: "Your account", title: "Profile" },
];

const SIDEBAR_KEY = "siamsil-sidebar-collapsed";
const NAV_GROUPS = [
  { label: "Explore", hrefs: ["/", "/library", "/zomidictionary", "/bible", "/learning"] },
  { label: "Language tools", hrefs: ["/zomitranslate", "/chat"] },
  { label: "Account", hrefs: ["/profile"] },
];

function MenuIcon() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function BrandLogo({ size = 38 }: { size?: number }) {
  return (
    <span className="shell-brand-logo-wrap" style={{ width: size, height: size }}>
      <Image src="/logo.png" alt="" width={size} height={size} className="shell-brand-logo" priority unoptimized />
    </span>
  );
}

function Navigation({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <nav className="side-panel-nav" aria-label="Primary navigation">
      {NAV_GROUPS.map((group) => (
        <div className="side-panel-group" key={group.label}>
          <span className="side-panel-group-label">{group.label}</span>
          {group.hrefs.map((href) => {
            const item = NAV_TABS.find((tab) => tab.href === href)!;
            const { Icon, label, hint } = item;
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`side-panel-item${active ? " active" : ""}`}
                title={label}
                aria-label={label}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
              >
                <span className="side-panel-icon"><Icon size={19} filled={active} /></span>
                <span className="side-panel-copy">
                  <span className="side-panel-label">{label}</span>
                  <span className="side-panel-hint">{hint}</span>
                </span>
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export default function SidebarNav({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [collapseReady, setCollapseReady] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const page = PAGE_META.find(({ match }) => match.test(pathname)) ?? PAGE_META[0];

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setCollapsed(localStorage.getItem(SIDEBAR_KEY) === "true");
      setCollapseReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (collapseReady) localStorage.setItem(SIDEBAR_KEY, String(collapsed));
  }, [collapsed, collapseReady]);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    const frame = window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        menuButtonRef.current?.focus();
      } else if (event.key === "Tab") {
        const controls = drawerRef.current?.querySelectorAll<HTMLElement>("a, button");
        if (!controls?.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileOpen]);

  const closeDrawer = () => {
    setMobileOpen(false);
    menuButtonRef.current?.focus();
  };

  return (
    <>
      <header className="shell-topbar">
        <div className="shell-topbar-inner">
          <button
            type="button"
            className="shell-menu-btn shell-menu-mobile"
            ref={menuButtonRef}
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
          >
            <MenuIcon />
          </button>

          <div className="shell-topbar-leading">
            <button
              type="button"
              className="shell-menu-btn shell-menu-desktop"
              onClick={() => setCollapsed((value) => !value)}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-controls="siamsil-desktop-sidebar"
              aria-expanded={!collapsed}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <MenuIcon />
            </button>
            <Link href="/" className="shell-brand shell-brand-desktop" aria-label="Siamsil home">
              <BrandLogo size={38} />
              <span className="shell-brand-text">
                <span className="font-playfair shell-brand-title">SIAMSIL</span>
                <span className="shell-brand-sub">The Art of Literature</span>
              </span>
            </Link>
          </div>

          <Link href="/" className="shell-brand shell-brand-mobile" aria-label="Siamsil home">
            <BrandLogo size={38} />
            <span className="shell-brand-text">
              <span className="font-playfair shell-brand-title">SIAMSIL</span>
              <span className="shell-brand-sub">The Art of Literature</span>
            </span>
          </Link>

          <div className="shell-page-context">
            <span className="shell-page-eyebrow">{page.eyebrow}</span>
            <span className="font-playfair shell-page-title">{page.title}</span>
          </div>

          <Link href="/zomidictionary" className="shell-topbar-search" aria-label="Search dictionary">
            <IconSearch size={16} />
            <span className="shell-topbar-search-text">Search words</span>
          </Link>
        </div>
      </header>

      <div className="app-shell">
        <aside id="siamsil-desktop-sidebar" className={`desktop-sidebar${collapsed ? " collapsed" : ""}`} aria-label="Primary">
          <Link href="/zomitranslate" className="sidebar-primary-action" title="Translate a phrase" aria-label="Translate a phrase">
            <IconTranslate size={21} />
            <span>Translate a phrase</span>
          </Link>
          <Navigation pathname={pathname} />
        </aside>

        <div className={`mobile-drawer-backdrop${mobileOpen ? " visible" : ""}`} onClick={closeDrawer} aria-hidden="true" />
        <aside ref={drawerRef} className={`mobile-drawer${mobileOpen ? " open" : ""}`} role="dialog" aria-modal={mobileOpen} aria-label="Mobile navigation" aria-hidden={!mobileOpen}>
          <div className="mobile-drawer-head">
            <Link href="/" className="sidebar-brand-link" onClick={() => setMobileOpen(false)}>
              <BrandLogo size={40} />
              <span className="sidebar-brand-copy">
                <span className="font-playfair sidebar-brand-title">SIAMSIL</span>
                <span className="sidebar-brand-sub">The Art of Literature</span>
              </span>
            </Link>
            <button type="button" className="side-panel-close" ref={closeButtonRef} onClick={closeDrawer} aria-label="Close navigation">
              <CloseIcon />
            </button>
          </div>
          <Navigation pathname={pathname} onNavigate={() => setMobileOpen(false)} />
          <div className="side-panel-foot">Literature in Zomi</div>
        </aside>

        <main className="app-main">{children}</main>
      </div>
    </>
  );
}
