import type { Metadata } from "next";

// Saved words and history live on the device; the page has nothing for search engines.
export const metadata: Metadata = {
  title: "Profile",
  robots: { index: false, follow: true },
};

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return children;
}
