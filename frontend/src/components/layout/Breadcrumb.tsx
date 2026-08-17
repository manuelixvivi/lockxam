import React from "react";
import { ChevronRight, Home } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ items }) => {
  return (
    <nav className="flex items-center gap-2 text-xs text-slate-400 mb-6 py-1">
      <Home className="w-3.5 h-3.5 text-slate-500" />
      {items.map((item, idx) => (
        <React.Fragment key={idx}>
          <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
          {item.href ? (
            <a href={item.href} className="hover:text-slate-200 transition-colors">
              {item.label}
            </a>
          ) : (
            <span className="font-semibold text-slate-200">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};
