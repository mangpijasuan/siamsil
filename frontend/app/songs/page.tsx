import type { Metadata } from "next";
import SongsClient from "@/components/SongsClient";

export const metadata: Metadata = {
  title: "Zomi Songs | Siamsil",
  description: "Browse authorized Zomi hymns and worship songs.",
};

export default function SongsPage() {
  return <SongsClient />;
}
