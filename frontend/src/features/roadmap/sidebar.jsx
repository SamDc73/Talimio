import React, { useState, useEffect } from "react";
import { useSidebar } from "./SidebarContext"; // Re-added import
import { CheckCircle, ChevronRight, Circle, Lock } from "lucide-react";
import { cn } from "@/lib/utils"; // Assuming this utility exists

// --- Data Type Definitions (Kept from original code) ---
/**
 * @typedef {Object} Lesson
 * @property {string} id
 * @property {string} title
 * @property {string} status // 'completed', 'locked', 'active', etc.
 *
 * @typedef {Object} Module
 * @property {string} id
 * @property {string} title
 * @property {string} status // 'completed', etc.
 * @property {Lesson[]} lessons
 */

// Renamed component to avoid potential conflicts if keeping the original
function UpdatedSidebarWithContext({ modules = [], onLessonClick, activeLessonId = null }) {
  // --- Context Integration ---
  const { isOpen } = useSidebar(); // Get visibility state from context

  // --- State and Logic (Kept from previous version) ---
  const [expandedModules, setExpandedModules] = useState(() => {
    // Initialize with the first module expanded if modules exist and sidebar is open
    return isOpen && modules.length > 0 ? [modules[0].id] : [];
  });

  // Effect to handle initial expansion when sidebar opens/modules load
  useEffect(() => {
    if (isOpen && modules.length > 0 && expandedModules.length === 0) {
      setExpandedModules([modules[0].id]);
    }
    // Optional: Collapse all when sidebar closes (if desired)
    // if (!isOpen) {
    //   setExpandedModules([]);
    // }
  }, [isOpen, modules]); // Rerun when isOpen or modules change

  const handleToggleModule = (moduleId) => {
    setExpandedModules((prev) =>
      prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]
    );
  };

  const isModuleCompleted = (module) => {
    return (
      module.status === "completed" ||
      (module.lessons?.every((l) => l.status === "completed") && module.lessons.length > 0)
    );
  };

  const completedModulesCount = modules?.filter(isModuleCompleted).length || 0;
  const totalModules = modules.length;
  const progress = totalModules ? Math.round((completedModulesCount / totalModules) * 100) : 0;

  // --- Conditional Rendering based on Context ---
  if (!isOpen) {
    return null; // Don't render anything if the sidebar should be closed
  }

  // --- Sidebar Layout & Styling (Dynamic: All Modules) ---
  return (
    <aside
      className="sticky top-0 z-20 h-screen w-[320px] flex flex-col bg-white border-r border-zinc-200"
      style={{ boxShadow: "0 4px 20px rgba(0, 0, 0, 0.05)" }}
    >
      {/* Progress Pill */}
      <div className="flex items-center gap-2 px-4 pt-4">
        <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full px-3 py-1">
          {progress}% Completed
        </span>
      </div>
      {/* Module Navigation List - Dynamic rendering of all modules */}
      <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
        {modules.map((module) => {
          const moduleComplete = isModuleCompleted(module);
          const isExpanded = expandedModules.includes(module.id);
          return (
            <div
              key={module.id}
              className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden"
            >
              {/* Section Header */}
              <button
                type="button"
                onClick={() => handleToggleModule(module.id)}
                className="flex items-center justify-between w-full px-4 py-3 text-left font-semibold text-base text-zinc-900 border-b border-zinc-100 rounded-t-2xl focus:outline-none"
                style={{ background: "#fff" }}
                aria-expanded={isExpanded}
              >
                {module.title}
                <ChevronRight className={`w-5 h-5 text-zinc-400 transition-transform duration-200 ${isExpanded ? "rotate-90 text-emerald-600" : "rotate-0"}`} />
              </button>
              {/* Steps List - Lessons */}
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
                          className={`text-left ${isLessonComplete ? "font-semibold text-emerald-700" : isActive ? "font-semibold text-emerald-700" : "text-zinc-800"}`}
                          style={{ background: "none", border: "none", padding: 0, cursor: isLocked ? "not-allowed" : "pointer" }}
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

export default UpdatedSidebarWithContext;
