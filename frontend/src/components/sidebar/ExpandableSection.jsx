import { ChevronRight } from "lucide-react";

/**
 * Expandable section component with header and collapsible content
 * Used for modules, chapters, or any hierarchical navigation
 */
function ExpandableSection({
  title,
  isExpanded,
  onToggle,
  headerContent,
  children,
  className = "",
  isActive = false,
}) {
  return (
    <div
      className={`rounded-2xl border ${
        isActive ? "border-emerald-200 bg-emerald-50/50" : "border-zinc-200 bg-white"
      } shadow-sm overflow-hidden ${className}`}
    >
      <div
        className="flex items-center gap-3 justify-between w-full px-4 py-3 text-left font-semibold text-base text-zinc-900 border-b border-zinc-100 rounded-t-2xl cursor-pointer"
        style={{ background: isActive ? "transparent" : "#fff" }}
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {headerContent}
          <span className="line-clamp-2">{title}</span>
        </div>
        <ChevronRight
          className={`w-5 h-5 text-zinc-400 transition-transform duration-200 ${
            isExpanded ? "rotate-90 text-emerald-600" : "rotate-0"
          }`}
        />
      </div>
      {isExpanded && children && <div className="px-4 py-2 space-y-2">{children}</div>}
    </div>
  );
}

export default ExpandableSection;