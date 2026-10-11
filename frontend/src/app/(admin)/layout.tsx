import React from "react";
import "../../styles/tokens-admin.css";

/**
 * Platform Admin route group. Deliberately separate from the customer shell: own theme, own
 * session scope, own guard. Nothing in here may import from the customer `(app)` layout.
 */
export default function AdminGroupLayout({ children }: { children: React.ReactNode }) {
  return <div className="admin-theme min-h-screen bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white">{children}</div>;
}
