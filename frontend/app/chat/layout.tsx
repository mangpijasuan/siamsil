import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Siamsil AI",
  description: "Ask about Zomi words and phrases. Answers come only from Siamsil's dictionary, Bible, and stored translations.",
  alternates: { canonical: "/chat" },
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return children;
}
