import LearningClient from "@/components/LearningClient";
import { getLearningGroups } from "@/lib/api";
import "./learning.css";

export default async function LearningPage() {
  let groups: Record<string, import("@/lib/api").LearningEntry[]> = {};
  let error: string | null = null;

  try {
    const data = await getLearningGroups();
    groups = data.groups;
  } catch {
    error = "Learning collections could not be loaded. Check your connection and try again.";
  }

  return <LearningClient groups={groups} error={error} />;
}
