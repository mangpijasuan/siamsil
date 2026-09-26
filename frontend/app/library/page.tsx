import type { Metadata } from "next";
import LibraryClient from "@/components/LibraryClient";

export const metadata: Metadata = {
  title: "Zomi Library",
  description: "Explore Zomi books, scripture, language resources, and cultural archives in the Siamsil Library.",
};

export default function LibraryPage() {
  return <LibraryClient />;
}
