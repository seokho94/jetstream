"use client";

import { useEffect, useState } from "react";

const KEY = "jetstream.onboarded";

/** One-time dismissible intro that explains the product to first-time users. */
export function Onboarding() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      setShow(!localStorage.getItem(KEY));
    } catch {
      /* ignore */
    }
  }, []);

  if (!show) return null;

  function dismiss() {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  return (
    <div className="intro">
      <button className="intro-x" onClick={dismiss} aria-label="닫기" type="button">
        ×
      </button>
      <b>세계의 흐름을, 한눈에.</b>
      <p>
        수많은 헤드라인 대신 그 아래 흐르는 10–15개 거시 <b>흐름(current)</b>과 그 <b>방향(모멘텀)</b>을 봅니다. 흐름을
        누르면 상세·근거 기사가, 주간 <b>다이제스트</b>에서 한 주의 변화가 보여요.
      </p>
    </div>
  );
}
