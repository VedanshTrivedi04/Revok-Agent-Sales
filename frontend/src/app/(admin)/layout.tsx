import React from "react";
import "../../styles/tokens-admin.css";

/**
 * Platform Admin route group. Deliberately separate from the customer shell: own theme, own
 * session scope, own guard. Nothing in here may import from the customer `(app)` layout.
 */
export default function AdminGroupLayout({ children }: { children: React.ReactNode }) {
  return <div className="admin-theme min-h-screen bg-[#F2F5F3] dark:bg-[#070B11] text-slate-900 dark:text-slate-100 selection:bg-[#0D3B36] selection:text-white transition-colors duration-150">{children}</div>;
}
