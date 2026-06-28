"use client";

import { usePathname } from "next/navigation";

// Phase 0: Digest points at the latest built issue.
const DIGEST_ISSUE = 202626;

export function TabBar() {
  const p = usePathname() || "/";
  const onCurrents = p === "/" || p.startsWith("/board") || p.startsWith("/current");
  const onFollowing = p.startsWith("/following");
  const onDigest = p.startsWith("/digest");
  const onSearch = p.startsWith("/search");
  return (
    <nav className="tabbar">
      <a href="/board" className={onCurrents ? "active" : ""}>
        Currents
      </a>
      <a href="/following" className={onFollowing ? "active" : ""}>
        Following
      </a>
      <a href={`/digest/${DIGEST_ISSUE}`} className={onDigest ? "active" : ""}>
        Digest
      </a>
      <a href="/search" className={onSearch ? "active" : ""}>
        Search
      </a>
    </nav>
  );
}
