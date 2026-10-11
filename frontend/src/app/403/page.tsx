import React from "react";
import { Forbidden403 } from "../../components/layout/forbidden-403";

export default async function ForbiddenPage(props: { searchParams: Promise<{ scope?: string }> }) {
  const { scope } = await props.searchParams;
  const platform = scope === "platform";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      {platform ? (
        <Forbidden403
          title="Customer workspaces are off limits for platform accounts."
          description="Superadmin accounts only use the Platform Admin portal. Customer data and impersonation are not available."
          homeHref="/admin/orgs"
          homeLabel="Back to Platform Admin"
        />
      ) : (
        <Forbidden403 />
      )}
    </div>
  );
}
