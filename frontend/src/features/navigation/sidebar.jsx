import { CheckCircle, ChevronRight, Circle } from "lucide-react";
import { useEffect, useState } from "react";
import { useSidebar } from "./SidebarContext";

/**
 * @typedef {Object} Lesson - Course lesson with completion status
 * @property {string} id - Unique identifier
 * @property {string} title - Lesson title
 * @property {string} status - Status: 'completed', 'locked', or 'active'
 *
 * @typedef {Object} Module - Course module containing lessons
 * @property {string} id - Unique identifier
 * @property {string} title - Module title
 * @property {string} status - Module status
 * @property {Lesson[]} lessons - Array of lessons in this module
 */

/**
 * Course navigation sidebar that displays a hierarchical view of modules and lessons
 *
 * Features:
 * - Collapsible module sections with expand/collapse functionality
 * - Visual indicators for lesson completion status
 * - Progress tracking for overall course completion
 * - Responsive design that can be toggled via SidebarContext
 * - Auto-expands first module when sidebar opens
 *
 * @param {Object} props
 * @param {Module[]} props.modules - Array of course modules to display
 * @param {Function} props.onLessonClick - Callback when lesson is clicked, receives (moduleId, lessonId)
 * @param {string|null} props.activeLessonId - Currently active lesson ID for highlighting
 */
function Sidebar({ modules = [], onLessonClick, activeLessonId = null }) {
  // Get sidebar visibility state from context
  const { isOpen } = useSidebar();

  // Track which modules are expanded
  const [expandedModules, setExpandedModules] = useState(() => {
    return isOpen && modules.length > 0 ? [modules[0].id] : [];
  });

  // Auto-expand first module when sidebar opens
  useEffect(() => {
    if (isOpen && modules.length > 0 && expandedModules.length === 0) {
      setExpandedModules([modules[0].id]);
    }
  }, [isOpen, modules, expandedModules.length]);

  const handleToggleModule = (moduleId) => {
    setExpandedModules((prev) =>
      prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId],
    );
  };

  /**
   * Determines if a module is completed based on either:
   * 1. Module has explicit "completed" status
   * 2. All lessons within module are marked as completed
   *
   * @param {Module} module - The module to check
   * @returns {boolean} True if module is considered complete
   */
  const isModuleCompleted = (module) => {
    return (
      module.status === "completed" ||
      (module.lessons?.every((l) => l.status === "completed") && module.lessons.length > 0)
    );
  };

  // Calculate overall progress percentage
  const completedModulesCount = modules?.filter(isModuleCompleted).length || 0;
  const totalModules = modules.length;
  const progress = totalModules ? Math.round((completedModulesCount / totalModules) * 100) : 0;
  return (
    <aside
      className={`fixed-sidebar flex flex-col bg-white border-r border-zinc-200 transition-all duration-300 ease-in-out ${
        isOpen ? "w-[320px] opacity-100 translate-x-0" : "w-0 opacity-0 -translate-x-full"
      }`}
      style={{ boxShadow: isOpen ? "0 4px 20px rgba(0, 0, 0, 0.05)" : "none" }}
    >
      {/* Progress indicator showing overall course completion percentage */}
      <div
        className={`flex items-center gap-2 px-4 pt-20 transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0"
        }`}
      >
        <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full px-3 py-1">
          {progress}% Completed
        </span>
      </div>
      {/* Scrollable module list with expandable lesson sections */}
      <nav
        className={`flex-1 p-3 space-y-4 overflow-y-auto transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0"
        }`}
      >
        {modules.map((module) => {
          // Check if this module is expanded
          const isExpanded = expandedModules.includes(module.id);
          return (
            <div key={module.id} className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
              {/* Module header with expand/collapse toggle */}
              <button
                type="button"
                onClick={() => handleToggleModule(module.id)}
                className="flex items-center justify-between w-full px-4 py-3 text-left font-semibold text-base text-zinc-900 border-b border-zinc-100 rounded-t-2xl focus:outline-none"
                style={{ background: "#fff" }}
                aria-expanded={isExpanded}
              >
                {module.title}
                <ChevronRight
                  className={`w-5 h-5 text-zinc-400 transition-transform duration-200 ${
                    isExpanded ? "rotate-90 text-emerald-600" : "rotate-0"
                  }`}
                />
              </button>
              {/* Module lessons with completion status indicators */}
              {isExpanded && (
                <ol className="px-4 py-2 space-y-2">
                  {module.lessons.map((lesson) => {
                    const isLessonComplete = lesson.status === "completed";
                    const isLocked = lesson.status === "locked";
                    const isActive = lesson.id === activeLessonId;
                    return (
                      <li key={lesson.id} className="flex items-start gap-3">
                        <span className="mt-0.5">
                          {isLessonComplete ? (
                            <CheckCircle className="w-5 h-5 text-emerald-500" />
                          ) : (
                            <Circle className="w-5 h-5 text-zinc-300" />
                          )}
                        </span>
                        <button
                          type="button"
                          className={`text-left ${
                            isLessonComplete
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
                          onClick={() => !isLocked && onLessonClick?.(module.id, lesson.id)}
                        >
                          {lesson.title}
                        </button>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

export default Sidebar;
