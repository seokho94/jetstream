// Phase 0 data access. The client reads only published view objects (spec §6).
// Here we return seed data so the screens render without a backend. In Phase 1,
// switch these to fetch the serving API (NEXT_PUBLIC_API_BASE) with ISR/ETag.
import {
  buildBoard,
  buildCurrentView,
  buildDigest,
  type BoardView,
  type CurrentView,
  type Digest,
} from "@meridian/shared";

export async function getBoard(): Promise<BoardView> {
  return buildBoard();
}

export async function getCurrent(id: string): Promise<CurrentView | null> {
  return buildCurrentView(id);
}

export async function getDigest(issue: number): Promise<Digest> {
  return buildDigest(issue);
}
