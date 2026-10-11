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
  const items = [
    { id: "risk", label: "Detect risk sooner" },
    { id: "expansion", label: "Find expansion opportunities" },
    { id: "action", label: "Take action with confidence" },
  ];

  return (
    <div className={`relative flex flex-col text-left select-none ${className}`}>
      {/* Title with subtle curved hand-drawn accent arrow */}
      <div className="relative mb-8 max-w-md">
        <h3 className="text-2xl sm:text-[28px] font-medium text-slate-900 tracking-tight leading-[1.25]">
          From scattered data to clearer decisions.
        </h3>
        {/* Delicate hand-drawn sketch arrow curving down into the branch */}
        <div className="absolute -bottom-6 right-2 sm:right-10 pointer-events-none">
          <svg
            className="w-16 h-8 text-slate-600 overflow-visible"
            viewBox="0 0 70 30"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M 5 6 C 25 4, 48 12, 60 22"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <path
              d="M 52 22 L 61 23 L 60 14"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Minimal Tree Diagram */}
      <div className="relative pl-10 sm:pl-12 py-2">
        {/* Smooth branching tree lines */}
        <svg
          className="absolute left-2 sm:left-3 top-0 w-8 h-full text-slate-300 pointer-events-none overflow-visible"
          viewBox="0 0 32 180"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {/* Main vertical trunk */}
          <line
            x1="8"
            y1="18"
            x2="8"
            y2="156"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />

          {/* Branch 1 to top */}
          <path
            d="M 8 18 C 16 18, 24 18, 32 18"
            stroke="currentColor"
            strokeWidth="1.5"
          />

          {/* Branch 2 to middle */}
          <path
            d="M 8 87 C 16 87, 24 87, 32 87"
            stroke="currentColor"
            strokeWidth="1.5"
          />

          {/* Branch 3 to bottom */}
          <path
            d="M 8 156 C 16 156, 24 156, 32 156"
            stroke="currentColor"
            strokeWidth="1.5"
          />
        </svg>

        {/* 3 Minimal Outcome Nodes */}
        <div className="space-y-8 sm:space-y-9">
          {items.map((item) => (
            <div
              key={item.id}
              className="group flex items-center gap-3.5 cursor-default transition-transform hover:translate-x-1"
            >
              {/* Luminous emerald dot */}
              <span className="relative flex h-3 w-3 shrink-0 items-center justify-center">
                <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-40 group-hover:animate-ping" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-100 group-hover:ring-emerald-200 transition-all" />
              </span>

              {/* Minimal Text */}
              <span className="text-base sm:text-lg font-medium text-slate-800 tracking-tight group-hover:text-emerald-950 transition-colors">
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
