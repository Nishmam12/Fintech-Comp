"use client";
// The signed-in person's role in this mandate, derived from the same state the server enforces rules on.
// owner: the mandate owner. manager: holds a grant that may be passed on. agent: any other holder.
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

export type Role = "owner" | "manager" | "agent";

export function useRole(): { role: Role; isOwner: boolean } {
  const { session } = useSession();
  const { state } = useMandate();
  const me = session?.principalId ?? "";
  const isOwner = !!state && state.mandate.owner_principal_id === me;
  const isManager = !isOwner && !!state?.grants.some((g) => g.holder_principal_id === me && g.scope.can_delegate);
  return { role: isOwner ? "owner" : isManager ? "manager" : "agent", isOwner };
}
