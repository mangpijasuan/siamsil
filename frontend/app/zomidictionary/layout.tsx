import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Zomi Dictionary",
  description:
    "Search the Zomi–English dictionary on Siamsil. Look up words, definitions, and Zomi translations.",
  alternates: { canonical: "/zomidictionary" },
};

export default function ZomiDictionaryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
