import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import BottomNav from "@/components/BottomNav";
import SidebarNav from "@/components/SidebarNav";
import { PREFERENCES_BOOT_SCRIPT } from "@/lib/bible/preferences";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "Siamsil — Zomi Dictionary & Translate",
    template: "%s | Siamsil",
  },
  description: SITE_DESCRIPTION,
  // Absolute links (canonical, social previews) need the public address; see lib/site.ts.
  ...(SITE_URL ? { metadataBase: new URL(SITE_URL) } : {}),
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: "Siamsil — Zomi Dictionary & Translate",
    description: SITE_DESCRIPTION,
    ...(SITE_URL ? { images: [{ url: "/logo-lockup.png", alt: "Siamsil" }] } : {}),
  },
  twitter: { card: "summary", title: "Siamsil — Zomi Dictionary & Translate", description: SITE_DESCRIPTION },
  keywords: [
    "Siamsil",
    "Zomi Dictionary",
    "Zomi Translate",
    "Zomi language",
    "Zomi Bible",
  ],
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} h-full`} suppressHydrationWarning>
      <head>
        {/* Bible reading settings (theme, text size) applied while the page is parsed, before first paint.
            Static script with no user input; the root layout is not re-rendered on client navigation. */}
        <script id="bible-preferences" dangerouslySetInnerHTML={{ __html: PREFERENCES_BOOT_SCRIPT }} />
      </head>
      <body>
        <SidebarNav>{children}</SidebarNav>
        <BottomNav />
      </body>
    </html>
  );
}
