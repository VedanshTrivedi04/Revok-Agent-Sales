"use client";

import { useEffect, useRef, useState } from "react";

/** Width of the element, kept current as the layout changes (SVG charts size themselves from it). */
export function useWidth<T extends HTMLElement>(initial = 640) {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(initial);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(240, Math.floor(el.getBoundingClientRect().width)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return { ref, width };
}
