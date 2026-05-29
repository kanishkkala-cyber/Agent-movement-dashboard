import { motion } from "framer-motion";
import { NavLink, Outlet } from "react-router-dom";

const nav = [
  { to: "/daily", label: "Daily Operations Overview", icon: "📊" },
  { to: "/tracking", label: "Repo Agent Tracking", icon: "📍" },
];

export function Shell() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 shrink-0 border-r border-slate-700/60 bg-slate-950/95 p-4">
        <div className="mb-8 px-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-sky-400/90">
            Field Operations
          </p>
          <h1 className="text-lg font-semibold text-white">Command Center</h1>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} className="block">
              {({ isActive }) => (
                <motion.span
                  whileHover={{ x: 4 }}
                  className={`flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                    isActive
                      ? "bg-sky-500/20 text-sky-100 shadow-[0_0_20px_rgba(56,189,248,0.25)] border border-sky-500/30"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100 border border-transparent"
                  }`}
                >
                  <span className="mr-2 text-base">{item.icon}</span>
                  {item.label}
                </motion.span>
              )}
            </NavLink>
          ))}
        </nav>
        <p className="mt-8 px-2 text-xs text-slate-500">
          Admin uploads run in Streamlit: <code className="text-slate-400">streamlit run app.py</code>
        </p>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }}>
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
}
