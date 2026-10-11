import React from "react";
import { Forbidden403 } from "../../components/layout/forbidden-403";

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <Forbidden403 />
    </div>
  );
}
