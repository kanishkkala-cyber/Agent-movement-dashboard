import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function GlassCard({
  children,
  className = "",
  title,
  subtitle,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`rounded-2xl border border-slate-600/40 bg-slate-900/55 shadow-card backdrop-blur-xl ${className}`}
      style={{ boxShadow: "0 0 0 1px rgba(148,163,184,0.06), 0 18px 50px rgba(0,0,0,0.45)" }}
    >
      {(title || subtitle) && (
        <div className="border-b border-slate-700/60 px-5 py-4">
          {title && <h3 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h3>}
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </motion.div>
  );
}
