import { permanentRedirect } from "next/navigation";

// The profile page became My Workspace (saved words, searches, Bible bookmarks, learning progress).
export default function ProfilePage() {
  permanentRedirect("/workspace");
}
