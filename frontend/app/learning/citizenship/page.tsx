import type { Metadata } from "next";
import CitizenshipTestClient from "@/components/CitizenshipTestClient";

export const metadata: Metadata = {
  title: "U.S. Citizenship Test",
  description: "Study U.S. naturalization civics questions in English, Zomi, and Burmese.",
};

export default function CitizenshipTestPage() {
  return <CitizenshipTestClient />;
}
