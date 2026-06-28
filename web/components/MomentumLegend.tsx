import { type MomentumState } from "@jetstream/shared";
import { MomentumBadge } from "./MomentumBadge";

const ORDER: MomentumState[] = ["rising", "peaking", "cooling", "steady"];
const MEANING: Record<MomentumState, string> = {
  rising: "상승 가속",
  peaking: "고점 평탄화",
  cooling: "관심 냉각",
  steady: "꾸준히 유지",
};

/** Explains the four momentum states (onboarding for first-time users). */
export function MomentumLegend() {
  return (
    <div className="legend-mom" aria-label="모멘텀 상태 설명">
      {ORDER.map((s) => (
        <div className="legend-item" key={s}>
          <MomentumBadge state={s} />
          <span className="legend-mean">{MEANING[s]}</span>
        </div>
      ))}
    </div>
  );
}
