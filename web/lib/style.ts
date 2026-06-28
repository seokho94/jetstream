import type { CSSProperties } from "react";

// Helper to set CSS custom properties (e.g. the per-current --c hue) inline.
export const vars = (v: Record<string, string | number>): CSSProperties =>
  v as unknown as CSSProperties;
