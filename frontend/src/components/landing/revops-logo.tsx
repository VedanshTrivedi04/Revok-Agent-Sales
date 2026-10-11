import React from "react";

export function RevOpsLogoIcon({ className = "w-7 h-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Three-node triangular connected hub matching RevOps Agent brandmark */}
      <circle cx="50" cy="22" r="13" fill="#16A34A" />
      <circle cx="24" cy="72" r="13" fill="#16A34A" />
      <circle cx="76" cy="72" r="13" fill="#16A34A" />
      
      {/* Central linking node / connector arms */}
      <path
        d="M50 35 C 50 48, 35 60, 24 60 C 24 60, 42 66, 50 54 C 58 66, 76 60, 76 60 C 65 60, 50 48, 50 35 Z"
        fill="#16A34A"
      />
      <circle cx="50" cy="50" r="7" fill="#16A34A" />
    </svg>
  );
}

export function RevOpsLogo({
  className = "",
  iconSize = "w-7 h-7",
  textSize = "text-lg",
}: {
  className?: string;
  iconSize?: string;
  textSize?: string;
}) {
  return (
    <div className={`flex items-center gap-2.5 font-bold tracking-tight text-[#0F172A] ${className}`}>
      <RevOpsLogoIcon className={iconSize} />
      <span className={`${textSize} font-bold tracking-tight`}>RevOps Agent</span>
    </div>
  );
}
