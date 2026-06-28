// Meridian design tokens — CANON §1–§3 + §14 R11 (confirmed colors).
// Keep web/app/globals.css in sync with these values.
import type { MomentumState } from "./types";

export const surfaces = {
  bg: "#0E1116",
  card: "#171C24",
  cardAlt: "#13171D",
  border: "#2C333D",
  ink: "#F2F4F7",
  secondary: "#9BA3AF",
  muted: "#6B7480",
} as const;

export const brand = {
  teal: "#34D0BA", // chrome + digest only
} as const;

export const status = {
  upGreen: "#6FBF73",
  downRed: "#D08585",
  otherGrey: "#586170", // streamgraph 'Other' band (CANON R8)
} as const;

// Momentum state badge encoding (reserved hues; always color + icon + label).
export const momentum: Record<
  MomentumState,
  { hex: string; icon: string; labelEn: string; labelKo: string }
> = {
  rising: { hex: "#F5A524", icon: "ti-trending-up", labelEn: "Rising", labelKo: "상승" },
  peaking: { hex: "#FB7A50", icon: "ti-activity", labelEn: "Peaking", labelKo: "정점" },
  cooling: { hex: "#7C9CC0", icon: "ti-trending-down", labelEn: "Cooling", labelKo: "냉각" },
  steady: { hex: "#9BA3AF", icon: "ti-minus", labelEn: "Steady", labelKo: "안정" },
};

// Per-current hues — confirmed (CANON §14 R11). A current owns its detail screen's hue.
// None of these may equal a momentum state hue or brand teal.
export const currentHues: Record<string, { hex: string; hueName: string }> = {
  "ai-governance": { hex: "#C46BD8", hueName: "orchid" },
  "cost-of-living": { hex: "#E86A8E", hueName: "rose" },
  energy: { hex: "#9CCB3B", hueName: "lime" },
  "middle-east": { hex: "#5C6BC0", hueName: "indigo" },
  china: { hex: "#4EA8DE", hueName: "blue" },
  climate: { hex: "#8B7FE8", hueName: "violet" },
  // Phase 1+ candidates (QA gate on assignment):
  elections: { hex: "#D9C24A", hueName: "mustard" },
  trade: { hex: "#D85FB0", hueName: "magenta" },
  migration: { hex: "#3FB6C9", hueName: "cyan" },
  "tech-platforms": { hex: "#A074E6", hueName: "purple" },
  markets: { hex: "#3FBE86", hueName: "emerald" },
  defense: { hex: "#C77A6A", hueName: "clay" },
};

export function hueFor(colorKey: string): string {
  return currentHues[colorKey]?.hex ?? status.otherGrey;
}

export const typography = {
  // sharp sans-serif everywhere; serif only in the digest lede.
  sans: `-apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans KR", sans-serif`,
  serif: `Georgia, "Times New Roman", serif`,
} as const;
