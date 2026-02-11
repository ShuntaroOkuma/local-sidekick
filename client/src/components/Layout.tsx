import { NavLink, Outlet } from "react-router-dom";

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

export function Layout() {
  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <nav className="w-16 bg-gray-950 border-r border-gray-800 flex flex-col items-center gap-1">
        {/* Titlebar drag area (traffic lights region) */}
        <div className="titlebar-drag w-full h-12 shrink-0" />
        {/* App icon */}
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm mb-4">
          LS
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
