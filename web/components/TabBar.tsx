"use client";

import { usePathname } from "next/navigation";

// Phase 0: Digest points at the latest built issue; Following/Search are not wired yet.
const DIGEST_ISSUE = 202626;

export function TabBar() {
  const p = usePathname() || "/";
  const onCurrents = p === "/" || p.startsWith("/board") || p.startsWith("/current");
  const onDigest = p.startsWith("/digest");
  return (
    <nav className="tabbar">
      <a href="/board" className={onCurrents ? "active" : ""}>
        Currents
      </a>
      <span className="soon" aria-disabled>
        Following<i>곧</i>
      </span>
      <a href={`/digest/${DIGEST_ISSUE}`} className={onDigest ? "active" : ""}>
        Digest
      </a>
      <span className="soon" aria-disabled>
        Search<i>곧</i>
      </span>
    </nav>
  );
}
