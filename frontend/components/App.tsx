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
  { id: "mandate", label: "Mandate", title: "Mandate", hint: "Where the money is, and who may spend it." },
  { id: "ask", label: "Ask", title: "Ask for a payment", hint: "Send a request as an agent and see the kernel's decision." },
  { id: "review", label: "Review", title: "Review", hint: "Requests held for your approval." },
  { id: "activity", label: "Activity", title: "Activity", hint: "What the models cost and how they were routed." },
  { id: "attack", label: "Attack", title: "Attack lab", hint: "Run hostile agents against the kernel and watch it refuse." },
  { id: "settings", label: "Settings", title: "Settings", hint: "Your key and account." },
] as const;
type TabId = (typeof TABS)[number]["id"];

function Shell() {
  const { session, signOut } = useSession();
  const [tab, setTab] = useState<TabId>("mandate");
  if (!session) return <SignIn />;
  return (
    <MandateProvider>
      <div className="min-h-dvh lg:pl-64">
        <div className="mx-auto max-w-5xl px-4 pb-24 sm:px-6 lg:px-10 lg:pb-12">
          <header className="flex items-center justify-between py-4 lg:py-8">
            <div>
              <h1 className="fig text-xl lg:text-3xl">{TABS.find((t) => t.id === tab)?.title}</h1>
              <p className="hidden text-sm text-muted lg:block">{TABS.find((t) => t.id === tab)?.hint}</p>
            </div>
            <button onClick={signOut} className="btn-ghost lg:hidden">Sign out</button>
          </header>
          {tab === "mandate" && <MandateView />}
          {tab === "ask" && <AskView />}
          {tab === "review" && <ReviewView />}
          {tab === "activity" && <ActivityView />}
          {tab === "attack" && <SimulationView />}
          {tab === "settings" && <SettingsView />}
        </div>
      </div>
      <nav
        aria-label="Sections"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-card lg:inset-y-0 lg:right-auto lg:flex lg:w-64 lg:flex-col lg:border-0 lg:bg-ink lg:px-4 lg:py-6"
      >
        <div className="hidden lg:mb-8 lg:block lg:px-3">
          <p className="fig text-2xl text-white">Budget Kernel</p>
          <p className="mt-1 text-sm text-ink-text">Models propose. The kernel decides.</p>
        </div>
        <ul className="mx-auto flex max-w-3xl lg:mx-0 lg:flex-col lg:gap-1">
          {TABS.map((t) => {
            const on = tab === t.id;
            return (
              <li key={t.id} className="flex-1 lg:flex-none">
                <button
                  onClick={() => setTab(t.id)}
                  aria-current={on ? "page" : undefined}
                  className={`min-h-14 w-full text-sm transition-colors lg:min-h-11 lg:rounded-md lg:px-3 lg:text-left lg:text-base ${
                    on
                      ? "font-semibold text-accent lg:bg-ink-soft lg:text-white"
                      : "text-muted lg:text-ink-text lg:hover:bg-ink-soft"
                  }`}
                >
                  {t.label}
                </button>
              </li>
            );
          })}
        </ul>
        <div className="mt-auto hidden px-3 lg:block">
          <p className="text-sm text-ink-text">Signed in as {session.kind ?? "user"}</p>
          <button onClick={signOut} className="mt-2 min-h-11 w-full rounded-md border border-ink-soft px-3 text-sm text-ink-text transition-colors hover:bg-ink-soft hover:text-white">
            Sign out
          </button>
        </div>
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
