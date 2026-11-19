import type { Metadata } from "next";
import WorkspaceClient from "@/components/WorkspaceClient";
import "./workspace.css";

export const metadata: Metadata = {
  title: "My Workspace",
  description: "Your saved Zomi words, searches, Bible bookmarks and learning progress, kept in your browser.",
  alternates: { canonical: "/workspace" },
  robots: { index: false }, // a personal page: nothing in it is the same for two visitors
};

export default function WorkspacePage() {
  return <WorkspaceClient />;
}
