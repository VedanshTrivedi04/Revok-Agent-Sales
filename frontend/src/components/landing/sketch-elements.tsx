import React from "react";

/**
 * Hand-drawn SVG arrows and sketch annotations for the RevOps landing page.
 * Uses soft curved bezier paths and organic stroke width to mimic real ink sketches.
 */

export function HeroSketchAnnotation({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex items-center select-none pointer-events-none ${className}`}>
      <span className="font-handwriting text-xl text-slate-700 tracking-wide rotate-[-3deg] whitespace-nowrap">
        Connect scattered signals
      </span>
      <svg
        className="w-16 h-14 -mt-3 ml-1 text-slate-700 overflow-visible"
        viewBox="0 0 70 60"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Curved arrow pointing up and left */}
        <path
          d="M 55 50 C 50 25, 30 15, 12 18"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeDasharray="0.5 0"
        />
        {/* Hand-drawn arrowhead */}
        <path
          d="M 22 10 L 10 18 L 18 27"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export function ProblemSketchAnnotation({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex items-center select-none pointer-events-none ${className}`}>
      <div className="flex flex-col">
        <span className="font-handwriting text-lg text-slate-600 leading-tight rotate-[-4deg] max-w-[200px]">
          The information exists but the story is fragmented
        </span>
      </div>
      <svg
        className="w-20 h-14 -mt-2 ml-2 text-slate-600 overflow-visible"
        viewBox="0 0 90 60"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Curved arrow curving right-up */}
        <path
          d="M 10 42 C 35 48, 60 40, 75 16"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        {/* Arrowhead */}
        <path
          d="M 64 22 L 76 15 L 77 28"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export function ExampleSketchAnnotation({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex items-center select-none pointer-events-none ${className}`}>
      <svg
        className="w-16 h-12 text-slate-700 mr-1 overflow-visible"
        viewBox="0 0 70 50"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Curved arrow pointing left towards the recommendation */}
        <path
          d="M 60 38 C 45 42, 28 32, 14 16"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        {/* Arrowhead */}
        <path
          d="M 23 11 L 12 16 L 18 26"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="font-handwriting text-xl text-slate-700 tracking-wide rotate-[3deg] whitespace-nowrap">
        Turn signals into action
      </span>
    </div>
  );
}

export function CtaDecisionBranch({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex flex-col ${className}`}>
      {/* Hand-drawn note */}
      <div className="flex items-center gap-2 mb-4">
        <span className="font-handwriting text-xl text-slate-700 rotate-[-2deg]">
          From scattered data to clearer decisions.
        </span>
        <svg
          className="w-12 h-6 text-slate-700 overflow-visible"
          viewBox="0 0 50 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M 5 12 C 20 8, 32 16, 44 14"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <path
            d="M 38 9 L 45 14 L 39 18"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Decision branching tree diagram */}
      <div className="relative pl-6 py-2">
        {/* Branching SVG curves */}
        <svg
          className="absolute left-0 top-0 w-8 h-full text-slate-400 overflow-visible"
          viewBox="0 0 32 140"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {/* Main trunk */}
          <line x1="8" y1="16" x2="8" y2="124" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" />
          
          {/* Branch 1 to top */}
          <path d="M 8 20 C 18 20, 24 20, 32 20" stroke="currentColor" strokeWidth="1.5" />
          
          {/* Branch 2 to middle */}
          <path d="M 8 70 C 18 70, 24 70, 32 70" stroke="currentColor" strokeWidth="1.5" />
          
          {/* Branch 3 to bottom */}
          <path d="M 8 120 C 18 120, 24 120, 32 120" stroke="currentColor" strokeWidth="1.5" />
        </svg>

        {/* 3 Outcome nodes */}
        <div className="space-y-6 pl-4">
          <div className="flex items-center gap-3 group">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400/50 group-hover:scale-125 transition-transform" />
            <span className="text-sm font-semibold text-slate-800">
              Detect risk sooner
            </span>
          </div>

          <div className="flex items-center gap-3 group">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400/50 group-hover:scale-125 transition-transform" />
            <span className="text-sm font-semibold text-slate-800">
              Find expansion opportunities
            </span>
          </div>

          <div className="flex items-center gap-3 group">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400/50 group-hover:scale-125 transition-transform" />
            <span className="text-sm font-semibold text-slate-800">
              Take action with confidence
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
