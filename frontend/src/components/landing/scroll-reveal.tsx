"use client";

import React, { useEffect, useRef, useState } from "react";

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  direction?: "up" | "down" | "left" | "right" | "fade" | "scale";
  threshold?: number;
}

export function ScrollReveal({
  children,
  className = "",
  delayMs = 0,
  direction = "up",
  threshold = 0.12,
}: ScrollRevealProps) {
  const [isVisible, setIsVisible] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = elementRef.current;
    if (!el) return;

    // Fallback if IntersectionObserver is not supported
    if (typeof window !== "undefined" && !("IntersectionObserver" in window)) {
      setIsVisible(true);
      return;
    }

    // Safety fallback: reveal element even if intersection observer fails to trigger
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, 1200);

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          clearTimeout(timer);
          observer.unobserve(el);
        }
      },
      {
        threshold: 0.01,
        rootMargin: "100px 0px 100px 0px",
      }
    );

    observer.observe(el);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [threshold]);

  const getTransformStyle = () => {
    if (isVisible) return "opacity-100 translate-x-0 translate-y-0 scale-100";
    
    switch (direction) {
      case "up":
        return "opacity-0 translate-y-10";
      case "down":
        return "opacity-0 -translate-y-10";
      case "left":
        return "opacity-0 translate-x-10";
      case "right":
        return "opacity-0 -translate-x-10";
      case "scale":
        return "opacity-0 scale-95";
      case "fade":
      default:
        return "opacity-0";
    }
  };

  return (
    <div
      ref={elementRef}
      style={{
        transitionDuration: "700ms",
        transitionDelay: `${delayMs}ms`,
        transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
      }}
      className={`transition-all will-change-transform ${getTransformStyle()} ${className}`}
    >
      {children}
    </div>
  );
}

/**
 * Global Scroll Progress Bar displayed at the top of the viewport
 */
export function ScrollProgressBar() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight <= 0) return;
      const currentProgress = (window.scrollY / totalHeight) * 100;
      setProgress(Math.min(100, Math.max(0, currentProgress)));
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="fixed top-0 left-0 right-0 h-[3px] z-50 pointer-events-none bg-transparent">
      <div
        className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-[#143C2E] transition-all duration-75 ease-out shadow-xs shadow-emerald-500/50"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
