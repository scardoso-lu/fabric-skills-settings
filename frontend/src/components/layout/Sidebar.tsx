"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/skills", label: "Skills", icon: "🎯" },
  { href: "/content", label: "Content", icon: "📄" },
  { href: "/graph", label: "Graph", icon: "🔗" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout(); // clears httpOnly cookie via POST /api/auth/logout
    router.push("/login");
  }

  return (
    <aside className="w-56 min-h-screen bg-base-200 flex flex-col py-4 px-2 shrink-0">
      <div className="px-3 mb-6">
        <h1 className="text-lg font-bold tracking-tight">fabric admin</h1>
        <p className="text-xs text-base-content/50">server manager</p>
      </div>

      <ul className="menu menu-sm flex-1 gap-0.5">
        {NAV_ITEMS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={pathname === item.href ? "active" : ""}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          </li>
        ))}
      </ul>

      <div className="px-2 mt-4">
        <button
          type="button"
          className="btn btn-ghost btn-sm w-full justify-start"
          onClick={handleLogout}
        >
          🚪 Logout
        </button>
      </div>
    </aside>
  );
}
