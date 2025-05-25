import { CheckCircle, ChevronRight, Circle } from "lucide-react";
import { useState, useEffect } from "react";
import { useSidebar } from "./SidebarContext";
import { useProgressSafe } from "../../hooks/useProgress";

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
 * - First module expanded by default, but users can collapse all modules if desired
 * - Connects to backend progress API to track lesson completion
 *
 * @param {Object} props
 * @param {Module[]} props.modules - Array of course modules to display
 * @param {Function} props.onLessonClick - Callback when lesson is clicked, receives (moduleId, lessonId)
 * @param {string|null} props.activeLessonId - Currently active lesson ID for highlighting
 * @param {string} props.courseId - ID of the current course
 */
function Sidebar({ modules = [], onLessonClick, activeLessonId = null, courseId }) {
  // Get sidebar visibility state from context
  const { isOpen } = useSidebar();

  // Use progress hook to connect to backend (safe version for non-course contexts)
  const { courseProgress, toggleLessonCompletion, isLessonCompleted } = useProgressSafe();

  const [expandedModules, setExpandedModules] = useState(() => {
    // Only expand the first module by default if there are modules and the sidebar is open
    return isOpen && modules.length > 0 ? [modules[0].id] : [];
  });

  const handleToggleModule = (moduleId) => {
    setExpandedModules((prev) =>
      prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]
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
      (module.lessons?.every((l) => isLessonCompleted(l.id)) && module.lessons.length > 0)
    );
  };

  // Use progress percentage from backend if available, otherwise calculate from modules
  const progress = courseProgress?.progress_percentage || 0;
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
                className="flex items-center gap-3 justify-between w-full px-4 py-3 text-left font-semibold text-base text-zinc-900 border-b border-zinc-100 rounded-t-2xl focus:outline-none"
                style={{ background: "#fff" }}
                aria-expanded={isExpanded}
              >
                <div className="flex items-center gap-3">
                  <div className="relative flex items-center justify-center">
                    <div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center">
                      <span className="text-sm text-zinc-600">{modules.indexOf(module) + 1}</span>
                    </div>
                    {/* Progress circle */}
                    {/* Only show progress circle if there's any progress */}
                    {module.lessons.length > 0 && module.lessons.some((l) => isLessonCompleted(l.id)) && (
                      <svg
                        className="absolute top-0 left-0 w-8 h-8 -rotate-90"
                        role="img"
                        aria-label={`Module progress: ${Math.round(
                          (module.lessons.filter((l) => isLessonCompleted(l.id)).length / module.lessons.length) * 100
                        )}%`}
                      >
                        <title>Module progress indicator</title>
                        <circle
                          cx="16"
                          cy="16"
                          r="14"
                          strokeWidth="2.5"
                          fill="none"
                          stroke="#f4f4f5"
                          className="opacity-70"
                        />
                        <circle
                          cx="16"
                          cy="16"
                          r="14"
                          strokeWidth="2.5"
                          fill="none"
                          stroke="#10b981"
                          strokeLinecap="round"
                          strokeDasharray={`${
                            (module.lessons.filter((l) => isLessonCompleted(l.id)).length / module.lessons.length) *
                            87.96
                          } 87.96`}
                          className="transition-all duration-300"
                          style={{
                            filter: "drop-shadow(0 1px 1px rgb(0 0 0 / 0.05))",
                          }}
                        />
                      </svg>
                    )}
                  </div>
                  <span>{module.title}</span>
                </div>
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
                    // Use backend status from our hook instead of local state
                    const isLocked = lesson.status === "locked";
                    const isActive = lesson.id === activeLessonId;
                    return (
                      <li key={lesson.id} className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!isLocked) {
                              toggleLessonCompletion(lesson.id);
                            }
                          }}
                          className="mt-0.5 transition-all duration-200 hover:scale-110"
                          disabled={isLocked}
                        >
                          {isLessonCompleted(lesson.id) ? (
                            <CheckCircle className="w-5 h-5 text-emerald-500" />
                          ) : (
                            <Circle
                              className={`w-5 h-5 ${
                                isLocked ? "text-zinc-200" : "text-zinc-300 hover:text-emerald-300"
                              }`}
                            />
                          )}
                        </button>
                        <button
                          type="button"
                          className={`text-left ${
                            isLessonCompleted(lesson.id)
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
