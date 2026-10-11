import { NextRequest, NextResponse } from "next/server";
import { SignJWT } from "jose";

const JWT_SECRET = new TextEncoder().encode(
  process.env.API_JWT_SECRET || "super-secret-development-jwt-service-key-32chars"
);

const MOCK_ORGS = [
  { id: "0192e21b-0001-7000-8000-000000000001", name: "Acme SaaS", role: "viewer" },
  { id: "0192e21b-0002-7000-8000-000000000002", name: "Globex Corp", role: "member" },
  { id: "0192e21b-0003-7000-8000-000000000003", name: "Initech Analytics", role: "admin" },
];

function getPermissionsForRole(role: string): string[] {
  switch (role) {
    case "owner":
      return [
        "view:accounts",
        "connect:own",
        "approve:own",
        "approve:any",
        "edit:card",
        "revert",
        "run:now",
        "rules:edit",
        "review:view",
        "runs:view",
        "integrations:manage",
        "mapping:edit",
        "autonomy:edit",
        "members:manage",
        "apikeys:manage",
        "data:export",
        "org:delete",
      ];
    case "admin":
      return [
        "view:accounts",
        "connect:own",
        "approve:own",
        "approve:any",
        "edit:card",
        "revert",
        "run:now",
        "rules:edit",
        "review:view",
        "runs:view",
        "integrations:manage",
        "mapping:edit",
        "autonomy:edit",
        "members:manage",
        "apikeys:manage",
        "data:export",
      ];
    case "manager":
      return [
        "view:accounts",
        "connect:own",
        "approve:own",
        "approve:any",
        "edit:card",
        "revert",
        "run:now",
        "rules:edit",
        "review:view",
        "runs:view",
      ];
    case "member":
      return [
        "view:accounts",
        "connect:own",
        "approve:own",
        "edit:card",
        "revert",
        "run:now",
      ];
    case "viewer":
    default:
      return ["view:accounts", "connect:own"];
  }
}

async function mintServiceJwt(sub: string, orgId: string, role: string, email: string) {
  return await new SignJWT({
    sub,
    org_id: orgId,
    role,
    email,
    aud: "revops-api",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(JWT_SECRET);
}

export async function GET(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  const endpoint = `/${path.join("/")}`;
  const url = new URL(req.url);

  const cookieRole = req.cookies.get("revops_mock_role")?.value;
  const queryRole = url.searchParams.get("mock_role");
  const role = queryRole || cookieRole || process.env.NEXT_PUBLIC_MOCK_ROLE || "viewer";

  const apiBase = process.env.NEXT_PUBLIC_API_BASE;

  // 1. If backend URL configured, try proxying directly
  if (apiBase) {
    try {
      const token = await mintServiceJwt(
        "0192e21b-0000-7000-8000-000000000001",
        "0192e21b-0001-7000-8000-000000000001",
        role,
        "finance.cro@acmesaas.com"
      );

      const targetUrl = `${apiBase}/api/v1${endpoint}${url.search}`;
      const forwardRes = await fetch(targetUrl, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      const data = await forwardRes.json().catch(() => null);
      if (data !== null) {
        return NextResponse.json(data, { status: forwardRes.status });
      }
    } catch {
      // Backend server currently offline/unreachable
    }
  }

  // 2. Fallback only if backend is unreachable (ensuring dev environment doesn't break)
  if (endpoint === "/me") {
    const mockUser = {
      id: "0192e21b-0000-7000-8000-000000000001",
      email: "finance.cro@acmesaas.com",
      name: "Marcus Vance",
      avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=64&h=64&fit=crop&crop=faces&q=80",
      timezone: "America/New_York",
      notification_prefs: {
        digest_channel: "slack" as const,
        digest_hour: 9,
        digest_days: "weekdays" as const,
        alert_high: true,
        alert_assigned: true,
        alert_failed: true,
      },
    };

    const mockOrg = {
      id: "0192e21b-0001-7000-8000-000000000001",
      name: "Acme SaaS",
      status: "active" as const,
      plan: "Enterprise",
      timezone: "America/New_York",
      currency: "USD",
    };

    const meResponse = {
      user: mockUser,
      memberships: MOCK_ORGS.map((org) => ({
        org_id: org.id,
        org_name: org.name,
        role: (org.id === mockOrg.id ? role : org.role) as "owner" | "admin" | "manager" | "member" | "viewer",
      })),
      org: mockOrg,
      role: role as "owner" | "admin" | "manager" | "member" | "viewer",
      permissions: getPermissionsForRole(role),
      flags: {
        email_send: false,
        meeting_request: true,
        slack_approvals: true,
        prompt_variant: false,
      },
      onboarding: {
        steps: [
          { key: "hubspot", status: "done" as const },
          { key: "google", status: "done" as const },
          { key: "slack", status: "done" as const },
        ],
        first_findings_ready: true,
      },
    };

    return NextResponse.json(meResponse);
  }

  return NextResponse.json({ items: [], next_cursor: null });
}

export async function POST(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  const endpoint = `/${path.join("/")}`;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE;
  const role = req.cookies.get("revops_mock_role")?.value || "viewer";

  if (apiBase) {
    try {
      const body = await req.json().catch(() => ({}));
      const token = await mintServiceJwt(
        "0192e21b-0000-7000-8000-000000000001",
        "0192e21b-0001-7000-8000-000000000001",
        role,
        "finance.cro@acmesaas.com"
      );

      const forwardRes = await fetch(`${apiBase}/api/v1${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await forwardRes.json().catch(() => null);
      return NextResponse.json(data, { status: forwardRes.status });
    } catch {
      // Backend unreachable
    }
  }

  return NextResponse.json({ success: true });
}

export async function PATCH(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  const endpoint = `/${path.join("/")}`;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE;
  const role = req.cookies.get("revops_mock_role")?.value || "viewer";

  if (apiBase) {
    try {
      const body = await req.json().catch(() => ({}));
      const token = await mintServiceJwt(
        "0192e21b-0000-7000-8000-000000000001",
        "0192e21b-0001-7000-8000-000000000001",
        role,
        "finance.cro@acmesaas.com"
      );

      const forwardRes = await fetch(`${apiBase}/api/v1${endpoint}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await forwardRes.json().catch(() => null);
      return NextResponse.json(data, { status: forwardRes.status });
    } catch {
      // Backend unreachable
    }
  }

  return NextResponse.json({ ok: true });
}

export async function PUT(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  const endpoint = `/${path.join("/")}`;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE;
  const role = req.cookies.get("revops_mock_role")?.value || "viewer";

  if (apiBase) {
    try {
      const body = await req.json().catch(() => ({}));
      const token = await mintServiceJwt(
        "0192e21b-0000-7000-8000-000000000001",
        "0192e21b-0001-7000-8000-000000000001",
        role,
        "finance.cro@acmesaas.com"
      );

      const forwardRes = await fetch(`${apiBase}/api/v1${endpoint}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await forwardRes.json().catch(() => null);
      return NextResponse.json(data, { status: forwardRes.status });
    } catch {
      // Backend unreachable
    }
  }

  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  const endpoint = `/${path.join("/")}`;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE;
  const role = req.cookies.get("revops_mock_role")?.value || "viewer";

  if (apiBase) {
    try {
      const token = await mintServiceJwt(
        "0192e21b-0000-7000-8000-000000000001",
        "0192e21b-0001-7000-8000-000000000001",
        role,
        "finance.cro@acmesaas.com"
      );

      const forwardRes = await fetch(`${apiBase}/api/v1${endpoint}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      const data = await forwardRes.json().catch(() => null);
      return NextResponse.json(data, { status: forwardRes.status });
    } catch {
      // Backend unreachable
    }
  }

  return NextResponse.json({ ok: true });
}
