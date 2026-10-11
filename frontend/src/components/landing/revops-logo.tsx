import React from "react";

export function RevOpsLogoIcon({
  className = "w-7 h-7",
  dark = false,
  adaptive = false,
}: {
  className?: string;
  dark?: boolean;
  adaptive?: boolean;
}) {
  if (adaptive) {
    return (
      <span className={`inline-flex items-center shrink-0 ${className}`}>
        <img
          src="/primary logo.png"
          alt="Revora Logo"
          className="w-full h-full object-contain dark:hidden shrink-0"
        />
        <img
          src="/secondary logo.png"
          alt="Revora Logo"
          className="w-full h-full object-contain hidden dark:inline-block shrink-0"
        />
      </span>
    );
  }

  return (
    <img
      src={dark ? "/secondary logo.png" : "/primary logo.png"}
      alt="Revora Logo"
      className={`${className} object-contain inline-block shrink-0`}
    />
  );
}

export function RevOpsLogo({
  className = "",
  iconSize = "w-7 h-7",
  textSize = "text-lg",
  nameHeight = "h-7",
  dark = false,
  adaptive = false,
  showNameImage = true,
}: {
  className?: string;
  iconSize?: string;
  textSize?: string;
  nameHeight?: string;
  dark?: boolean;
  adaptive?: boolean;
  showNameImage?: boolean;
}) {
  if (adaptive) {
    return (
      <div
        className={`flex items-center gap-2.5 font-bold tracking-tight text-slate-900 dark:text-white ${className}`}
      >
        <RevOpsLogoIcon className={iconSize} adaptive />
        {showNameImage ? (
          <>
            <img
              src="/pr name.png"
              alt="Revora"
              className={`${nameHeight} w-auto object-contain dark:hidden shrink-0`}
            />
            <img
              src="/sc name.png"
              alt="Revora"
              className={`${nameHeight} w-auto object-contain hidden dark:inline-block shrink-0`}
            />
          </>
        ) : (
          <span className={`${textSize} font-bold tracking-tight`}>Revora</span>
        )}
        <span className="sr-only">Revora</span>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-2.5 font-bold tracking-tight ${
        dark ? "text-white" : "text-[#0F172A]"
      } ${className}`}
    >
      <RevOpsLogoIcon className={iconSize} dark={dark} />
      {showNameImage ? (
        <img
          src={dark ? "/sc name.png" : "/pr name.png"}
          alt="Revora"
          className={`${nameHeight} w-auto object-contain shrink-0`}
        />
      ) : (
        <span className={`${textSize} font-bold tracking-tight`}>Revora</span>
      )}
      <span className="sr-only">Revora</span>
    </div>
  );
}

// Named aliases for clean branding
export const RevoraLogo = RevOpsLogo;
export const RevoraLogoIcon = RevOpsLogoIcon;
