"use client";

import { useEffect, useMemo, useState } from "react";
import { flowAtCursor, framesOf, type FlowRun } from "./agent-flow";

/** Length of one visual beat (a step starting, or its result appearing). */
export const BEAT_MS = 650;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/**
 * Reveals the real events of a run one beat at a time so a person can follow them.
 *
 * `stageKey` identifies what is being staged (a run, or a replay of it); the reveal restarts when
 * it changes. With `enabled` false the real flow is returned as is. The flow can keep growing while
 * the reveal is running (live events): the cursor simply catches up and then follows in real time.
 */
export function useStagedFlow(flow: FlowRun | undefined, stageKey: string, enabled: boolean) {
  const frames = useMemo(() => framesOf(flow), [flow]);
  const [state, setState] = useState<{ key: string; cursor: number }>({ key: stageKey, cursor: 0 });

  const staging = enabled && !prefersReducedMotion();
  const cursor = !staging ? frames.length : state.key === stageKey ? state.cursor : 0;
  const caughtUp = cursor >= frames.length;

  useEffect(() => {
    if (!staging || cursor >= frames.length) return;
    const timer = setTimeout(
      () => setState({ key: stageKey, cursor: cursor + 1 }),
      cursor === 0 ? 120 : BEAT_MS,
    );
    return () => clearTimeout(timer);
  }, [staging, cursor, frames.length, stageKey]);

  const shown = useMemo(() => flowAtCursor(flow, cursor), [flow, cursor]);
  // `done` only flips once the reveal has reached the end of the real run.
  const shownFlow = shown && caughtUp ? flow : shown;
  return { flow: shownFlow, caughtUp, staging };
}
