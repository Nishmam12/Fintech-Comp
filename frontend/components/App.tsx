"use client";
import { useState } from "react";
import ActivityView from "@/components/ActivityView";
import AskView from "@/components/AskView";
import ReviewView from "@/components/ReviewView";
import MandateView from "@/components/MandateView";
import SimulationView from "@/components/SimulationView";
import SettingsView from "@/components/SettingsView";
import SignIn from "@/components/SignIn";
import { MandateProvider } from "@/lib/mandate";
import { SessionProvider, useSession } from "@/lib/session";

const TABS = [
  { id: "mandate", label: "Mandate" },
  { id: "ask", label: "Ask" },
  { id: "review", label: "Review" },
  { id: "activity", label: "Activity" },
  { id: "attack", label: "Attack" },
  { id: "settings", label: "Settings" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function Shell() {
  const { session, signOut } = useSession();
  const [tab, setTab] = useState<TabId>("mandate");
  if (!session) return <SignIn />;
  return (
    <MandateProvider>
      <div className="mx-auto min-h-dvh max-w-3xl px-4 pb-24">
        <header className="flex items-center justify-between py-4">
          <h1 className="text-lg font-semibold">Budget Kernel</h1>
          <button onClick={signOut} className="btn-ghost">Sign out</button>
        </header>
        {tab === "mandate" && <MandateView />}
        {tab === "ask" && <AskView />}
        {tab === "review" && <ReviewView />}
        {tab === "activity" && <ActivityView />}
        {tab === "attack" && <SimulationView />}
        {tab === "settings" && <SettingsView />}
      </div>
      <nav className="fixed inset-x-0 bottom-0 border-t border-line bg-card">
        <ul className="mx-auto flex max-w-3xl">
          {TABS.map((t) => (
            <li key={t.id} className="flex-1">
              <button
                onClick={() => setTab(t.id)}
                aria-current={tab === t.id ? "page" : undefined}
                className={`min-h-14 w-full text-sm ${tab === t.id ? "font-semibold text-accent" : "text-muted"}`}
              >
                {t.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </MandateProvider>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  );
}
