import { NavLink, Outlet } from "react-router-dom";
import { useEngineState } from "../hooks/useEngineState";
import type { UserState } from "../lib/types";

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/timeline", label: "Timeline", icon: "📅" },
  { path: "/report", label: "Report", icon: "📝" },
  { path: "/settings", label: "Settings", icon: "⚙️" },
];

const STATE_COLORS: Record<UserState | "disconnected", string> = {
  focused: "bg-green-500",
  drowsy: "bg-red-500",
  distracted: "bg-yellow-400",
  away: "bg-gray-400",
  disconnected: "bg-gray-600",
};

const STATE_LABELS: Record<UserState | "disconnected", string> = {
  focused: "Focused",
  drowsy: "Drowsy",
  distracted: "Distracted",
  away: "Away",
  disconnected: "Disconnected",
};

export function Layout() {
  const { state, connected } = useEngineState();
  const currentState: UserState | "disconnected" = connected && state ? state.state : "disconnected";

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <nav className="w-16 bg-gray-950 border-r border-gray-800 flex flex-col items-center gap-1">
        {/* Titlebar drag area (traffic lights region) */}
        <div className="titlebar-drag w-full h-12 shrink-0" />
        {/* Status indicator */}
        <div className="mb-4 flex flex-col items-center gap-1" title={STATE_LABELS[currentState]}>
          <span className="text-[10px] font-semibold tracking-widest text-gray-500" style={{ writingMode: "vertical-rl" }}>
            SIDEKICK
          </span>
          <div className={`w-1.5 h-1.5 rounded-full ${STATE_COLORS[currentState]} transition-colors duration-500`} />
        </div>

        {/* Nav items */}
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `w-12 h-12 rounded-xl flex flex-col items-center justify-center gap-0.5 transition-colors ${
                isActive
                  ? "bg-gray-800 text-white"
                  : "text-gray-500 hover:text-gray-300 hover:bg-gray-800/50"
              }`
            }
            title={item.label}
          >
            <span className="text-lg">{item.icon}</span>
            <span className="text-[9px] leading-none">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Draggable titlebar area */}
        <div className="titlebar-drag h-8 shrink-0" />
        <main className="flex-1 overflow-y-auto">
          <div className="px-6 pb-6 max-w-2xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
