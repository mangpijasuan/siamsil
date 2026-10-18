import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import BottomNav from "@/components/BottomNav";
import SidebarNav from "@/components/SidebarNav";
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
    <html lang="en" className={`${inter.variable} ${playfair.variable} h-full`}>
      <body>
        <SidebarNav>{children}</SidebarNav>
        <BottomNav />
      </body>
    </html>
  );
}
