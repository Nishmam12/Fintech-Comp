"use client";
import { useEffect, useState } from "react";
import ActivityView, { native as activityNative } from "@/components/ActivityView";
import AskView from "@/components/AskView";
import ReviewView, { native as reviewNative } from "@/components/ReviewView";
import MandateView from "@/components/MandateView";
import SimulationView, { native as attackNative } from "@/components/SimulationView";
import SettingsView, { native as settingsNative } from "@/components/SettingsView";
import SetupView from "@/components/SetupView";
import SignIn from "@/components/SignIn";
import Tour, { type TourStep } from "@/components/Tour";
import Section from "@/components/ui/Section";
import { ToastProvider } from "@/components/Toast";
import { MandateProvider, useMandate } from "@/lib/mandate";
import { useRole } from "@/lib/role";
import { SessionProvider, useSession } from "@/lib/session";

const TABS: readonly { id: string; label: string; tab?: string; title: string; hint: string }[] = [
  { id: "mandate", label: "Mandate", title: "Mandate", hint: "Where the money is, and who may spend it." },
  { id: "ask", label: "Ask", title: "Ask for a payment", hint: "Send a request as an agent and see the kernel's decision." },
  { id: "review", label: "Review", title: "Review", hint: "Requests held for your approval." },
  { id: "activity", label: "Activity", title: "Activity", hint: "What the models cost and how they were routed." },
  { id: "attack", label: "Attack", tab: "Attack lab", title: "Attack lab", hint: "Run hostile agents against the kernel and watch it refuse." },
  { id: "settings", label: "Settings", title: "Settings", hint: "Your key and account." },
];
type TabId = "mandate" | "ask" | "review" | "activity" | "attack" | "settings";

// What each role sees. The server enforces the same rules: only the owner approves or denies, and simulations are human-only.
const OWNER_TABS: TabId[] = ["mandate", "review", "activity", "attack", "settings"];
const HOLDER_TABS: TabId[] = ["mandate", "ask", "activity", "settings"];
// Screens whose first section is a full-width cheque above two halves (the grid gives the cheque its natural height).
const NATIVE_ROWS: TabId[] = ["mandate"];
const HELD_POLL_MS = 10_000;

// What the first-visit guide says about each tab. One line each, in plain words; the selector finds the tab on the desktop
// bar or the phone bar, whichever is showing.
const TAB_NOTE: Record<TabId, TourStep["text"]> = {
  mandate: { pre: "where the money is and ", hl: "who", post: " may spend it" },
  ask: { pre: "send a request and see the ", hl: "verdict", post: "" },
  review: { pre: "requests the kernel ", hl: "held", post: " for you to approve" },
  activity: { pre: "every ", hl: "decision", post: ", and what the models cost" },
  attack: { pre: "run ", hl: "hostile", post: " agents against the kernel" },
  settings: { pre: "your ", hl: "account", post: ", password or key" },
};
const SIGN_OUT_NOTE: TourStep["text"] = { pre: "end this ", hl: "session", post: "" };

function Frame() {
  const { session, signOut } = useSession();
  const { state, refresh } = useMandate();
  const [tab, setTab] = useState<TabId>("mandate");
  const { role, isOwner } = useRole();
  // Until the state arrives the role is unknown, so only the landing tab is offered (no flash of the wrong tabs or role).
  const ready = !!state;
  const visible = TABS.filter((t) => (ready ? (isOwner ? OWNER_TABS : HOLDER_TABS) : ["mandate"]).includes(t.id as TabId)) as (typeof TABS[number] & { id: TabId })[];
  const current = visible.find((t) => t.id === tab) ?? visible[0];
  const heldCount = isOwner ? (state?.transactions.filter((t) => t.state === "proposed").length ?? 0) : 0;

  // Keep the Review badge fresh while another tab is open (the Review screen polls on its own).
  useEffect(() => {
    if (!isOwner) return;
    const id = setInterval(() => { if (document.visibilityState === "visible") refresh(); }, HELD_POLL_MS);
    return () => clearInterval(id);
  }, [isOwner, refresh]);

  // Rebuilt views return their own <Section>s (exported `native = true`); the rest sit inside one full-width section.
  const view = {
    mandate: [<MandateView key="m" />, true], ask: [<AskView key="a" />, true],
    review: [<ReviewView key="r" />, reviewNative], activity: [<ActivityView key="v" />, activityNative],
    attack: [<SimulationView key="s" />, attackNative], settings: [<SettingsView key="t" />, settingsNative],
  }[current.id] as [React.ReactNode, boolean];
  const body = view[1] ? view[0] : (
    <Section span={12} title={current.title} meta={current.hint}><div className="pt-4">{view[0]}</div></Section>
  );
  const tourSteps: TourStep[] = [
    ...visible.map((t) => ({ selector: `nav.tabs a[href="#${t.id}"], nav.bottom a[href="#${t.id}"]`, text: TAB_NOTE[t.id] })),
    { selector: ".who a", text: SIGN_OUT_NOTE, extra: true },
  ];
  const badge = (t: TabId) =>
    t === "review" && heldCount > 0 ? <span className="count" aria-label={`${heldCount} waiting`}>{heldCount}</span> : null;

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><b className="fig">Budget Kernel</b><span>Models propose. The kernel decides.</span></div>
        <div className="who">
          <span>{session?.name ?? ""}</span>
          {ready && <span className="pill">{role[0].toUpperCase() + role.slice(1)}</span>}
          <a href="#signout" onClick={(e) => { e.preventDefault(); signOut(); }}>Sign out</a>
        </div>
      </header>
      <nav className="tabs" aria-label="Sections">
        {visible.map((t) => (
          <a key={t.id} href={`#${t.id}`} aria-current={current.id === t.id ? "page" : undefined} className={current.id === t.id ? "on" : ""}
             onClick={(e) => { e.preventDefault(); setTab(t.id); }}>
            {t.tab ?? t.label}{badge(t.id)}
          </a>
        ))}
      </nav>
      {ready && <Tour kind={isOwner ? "owner" : "holder"} steps={tourSteps} />}
      <main className={`main ${NATIVE_ROWS.includes(current.id) ? "rows-auto-fill" : ""}`}>{body}</main>
      <nav className={`bottom ${visible.length === 4 ? "four" : ""}`} aria-label="Sections">
        {visible.map((t) => (
          <a key={t.id} href={`#${t.id}`} aria-current={current.id === t.id ? "page" : undefined} className={current.id === t.id ? "on" : ""}
             onClick={(e) => { e.preventDefault(); setTab(t.id); }}>
            {t.id === "attack" ? "Attack" : t.label}{badge(t.id)}
          </a>
        ))}
      </nav>
    </div>
  );
}

function NoMandate() {
  const { session, signOut } = useSession();
  return (
    <div className="app">
      <header className="top">
        <div className="brand"><b className="fig">Budget Kernel</b></div>
        <div className="who"><span>{session?.name ?? ""}</span><a href="#signout" onClick={(e) => { e.preventDefault(); signOut(); }}>Sign out</a></div>
      </header>
      <nav className="tabs" aria-label="Sections"><a href="#none" className="on" onClick={(e) => e.preventDefault()}>Mandate</a></nav>
      <main className="main">
        <Section span={12} title="No mandate yet" meta="Nothing to show">
          <div className="pt-4"><p>This account does not hold any grant in a mandate yet. The person who funds a mandate gives an agent a budget; until then there is nothing to show here. Sign in again once they have.</p></div>
        </Section>
      </main>
    </div>
  );
}

function Shell() {
  const { session } = useSession();
  if (!session) return <SignIn />;
  if (!session.mandateId) return session.kind === "human" ? <SetupView /> : <NoMandate />;
  return (
    <MandateProvider>
      <ToastProvider>
        <Frame />
      </ToastProvider>
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
