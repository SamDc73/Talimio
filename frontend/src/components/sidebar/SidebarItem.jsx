/**
 * Generic sidebar item component
 * Handles click events and active states
 */
function SidebarItem({
  title,
  isActive = false,
  isCompleted = false,
  isLocked = false,
  onClick,
  leftContent,
  rightContent,
  className = "",
}) {
  return (
    <li className={`flex items-start gap-3 ${className}`}>
      {leftContent}
      <button
        type="button"
        className={`text-left flex-1 min-w-0 ${
          isCompleted
            ? "font-semibold text-emerald-700"
            : isActive
            ? "font-semibold text-emerald-700"
            : "text-zinc-800"
        }`}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          cursor: isLocked ? "not-allowed" : "pointer",
        }}
        disabled={isLocked}
        onClick={() => !isLocked && onClick?.()}
      >
        {title}
      </button>
      {rightContent}
    </li>
  );
}

export default SidebarItem;