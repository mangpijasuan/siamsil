import type { Metadata } from "next";
import LearningClient from "@/components/LearningClient";
import { getLearningGroups } from "@/lib/api";

export const metadata: Metadata = {
  title: "Learn Zomi",
  description: "Learn everyday Zomi phrases reviewed by Zomi teachers, and practise for the U.S. citizenship test.",
  alternates: { canonical: "/learning" },
};

export default async function LearningPage() {
  let groups: Record<string, import("@/lib/api").LearningEntry[]> = {};
  let error: string | null = null;

  try {
    const data = await getLearningGroups();
    groups = data.groups;
  } catch {
    error = "Could not reach the API. Start the backend on port 8001.";
  }

  return <LearningClient groups={groups} error={error} />;
}
