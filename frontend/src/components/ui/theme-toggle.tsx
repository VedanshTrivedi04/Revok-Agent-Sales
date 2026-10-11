"use client";

import React, { useState, useRef, useEffect } from "react";
import { Sun, Moon, Laptop, Check } from "lucide-react";
import { useTheme } from "../../lib/theme/theme-context";

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 rounded-full text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors focus-visible:ring-2 focus-visible:ring-emerald-500"
        aria-label="Switch theme"
        title={`Theme: ${theme} (currently ${resolvedTheme})`}
        aria-expanded={isOpen}
      >
        {resolvedTheme === "dark" ? (
          <Moon className="w-4 h-4 text-emerald-400" />
        ) : (
          <Sun className="w-4 h-4 text-amber-500" />
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-36 rounded-2xl bg-white dark:bg-[#0D1522] border border-slate-200/90 dark:border-slate-800 shadow-xl z-50 p-1.5 space-y-0.5 text-xs">
          <button
            type="button"
            onClick={() => {
              setTheme("light");
              setIsOpen(false);
            }}
            className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl transition-colors ${
              theme === "light"
                ? "bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center gap-2">
              <Sun className="w-3.5 h-3.5 text-amber-500" />
              <span>Light</span>
            </div>
            {theme === "light" && (
              <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setTheme("dark");
              setIsOpen(false);
            }}
            className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl transition-colors ${
              theme === "dark"
                ? "bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center gap-2">
              <Moon className="w-3.5 h-3.5 text-emerald-400" />
              <span>Dark</span>
            </div>
            {theme === "dark" && (
              <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setTheme("system");
              setIsOpen(false);
            }}
            className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl transition-colors ${
              theme === "system"
                ? "bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center gap-2">
              <Laptop className="w-3.5 h-3.5 text-slate-400" />
              <span>System</span>
            </div>
            {theme === "system" && (
              <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}
