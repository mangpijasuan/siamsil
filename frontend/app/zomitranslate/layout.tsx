import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Zomi Translate",
  description:
    "Zomi Translate on Siamsil — look up English–Zomi pairs from Bible, dictionary, and daily use.",
  alternates: { canonical: "/zomitranslate" },
};

export default function ZomiTranslateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
