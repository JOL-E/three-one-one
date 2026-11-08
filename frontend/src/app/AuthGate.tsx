import type { ReactNode } from "react";

import { useMe } from "../api/queries";

/** Shows a way to log in until there's a session. No spinner: the ground color shows
 *  for the moment the check takes. Until M5 builds a login screen, the admin's login
 *  sets the session (DECISIONS #36). */
export function AuthGate({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <div className="bg-ground h-full" />;
  if (me.isError) {
    return (
      <div className="text-muted flex h-full items-center justify-center px-8 text-center">
        Can't reach 311 right now. Check the connection and try again.
      </div>
    );
  }
  if (me.data) return <>{children}</>;
  return (
    <div className="pt-edge flex h-full flex-col items-start justify-center gap-6 px-8">
      <div className="text-[56px] leading-none font-extrabold tracking-[-0.03em]">311</div>
      <p className="text-text-2 m-0 max-w-sm text-[17px]">An inbox for side-project ideas.</p>
      <a
        href="/admin/login/?next=/"
        className="label border-accent bg-accent text-on-accent inline-flex h-12 items-center border-2 px-6 text-[13px]"
      >
        Log in
      </a>
    </div>
  );
}
