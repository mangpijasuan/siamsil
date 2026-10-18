import type { Metadata } from "next";
import { Inter, Playfair_Display, Raleway } from "next/font/google";
import BottomNav from "@/components/BottomNav";
import SidebarNav from "@/components/SidebarNav";
import { PREFERENCES_BOOT_SCRIPT } from "@/lib/bible/preferences";
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

const raleway = Raleway({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: {
    default: "Siamsil — Zomi Dictionary & Translate",
    template: "%s | Siamsil",
  },
  description:
    "Siamsil — Zomi Dictionary, Translate, Bible, and Learning. The digital home for the Zomi language.",
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
    <html lang="en" className={`${inter.variable} ${playfair.variable} ${raleway.variable} h-full`} suppressHydrationWarning>
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
