"use client";
import MandateView from "@/components/MandateView";
import SignIn from "@/components/SignIn";
import { SessionProvider, useSession } from "@/lib/session";

function Shell() {
  const { session, signOut } = useSession();
  if (!session) return <SignIn />;
  return (
    <div className="mx-auto min-h-dvh max-w-2xl px-4 pb-8">
      <header className="flex items-center justify-between py-4">
        <h1 className="text-lg font-semibold">Budget Kernel</h1>
        <button onClick={signOut} className="btn-ghost">Sign out</button>
      </header>
      <MandateView />
    </div>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  );
}
