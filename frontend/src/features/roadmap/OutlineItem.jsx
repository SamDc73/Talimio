// OutlineItem.jsx
// Renders a single module card with its lessons (and sub-lessons if present)
// Mimics the styling of module cards in UI-update.txt
// Type hints are in comments for clarity

import { ArrowRight, CheckCircle } from "lucide-react"; // Using lucide-react as in UI-update.txt
import React, { useState } from "react";

// Helper function for class names (optional, but good practice)
const cn = (...classes) => classes.filter(Boolean).join(" ");

/**
 * @param {Object} props
 * @param {Object} props.module - The module object (with lessons)
 * @param {number} props.index - The module index (for numbering)
 * @param {Function} [props.onLessonClick] - Optional handler for lesson click
 * @param {Function} [props.isLessonCompleted] - Function to check if a lesson is completed
 * @param {Function} [props.toggleLessonCompletion] - Function to toggle lesson completion status
 * @param {Object} [props.courseProgress] - Course progress data
 * @returns {JSX.Element}
 */
function OutlineItem({ module, index, onLessonClick, isLessonCompleted, toggleLessonCompletion, courseProgress }) {
  // Use index + 1 for module ID if module.id is not present
  const moduleId = module.id ?? index + 1;
  // Keep track of expanded state based on module ID
  const [expanded, setExpanded] = useState(index === 0); // First module expanded by default

  // Calculate completed lessons (including nested ones) - Updated to use isLessonCompleted
  const countLessons = (items) => {
    let total = 0;
    let completed = 0;

    for (const item of items) {
      // Only count items that look like lessons (have a title)
      if (item && typeof item.title === "string") {
        total += 1;
        // Use isLessonCompleted function if available, otherwise fall back to status check
        if (isLessonCompleted?.(item.id) || item.status === "completed" || item.status === "done") {
          completed += 1;
        }
        // Recursively count nested lessons if they exist
        if (Array.isArray(item.lessons) && item.lessons.length > 0) {
          const [subTotal, subCompleted] = countLessons(item.lessons);
          total += subTotal;
          completed += subCompleted;
        }
      }
    }
    return [total, completed];
  };

  const [totalLessons, completedLessons] = countLessons(module.lessons || []);
  const progress = totalLessons > 0 ? (completedLessons / totalLessons) * 100 : 0;
  const isModuleCompleted = progress === 100 && totalLessons > 0; // Determine module completion based on progress

  // Component for a single lesson item
  const LessonItem = ({ lesson, idx, depth, parentIndexStr, onLessonClick }) => {
    const currentLessonIndexStr = parentIndexStr ? `${parentIndexStr}.${idx + 1}` : `${idx + 1}`;
    const isCompleted = isLessonCompleted?.(lesson.id) || lesson.status === "completed" || lesson.status === "done";
    const lessonKey = lesson.id ?? `${moduleId}-lesson-${depth}-${idx}`;

    return (
      <div
        key={lessonKey}
        className={`space-y-3 ${depth > 0 ? "ml-6 mt-3 border-l-2 border-emerald-100/50 pl-4 pt-3" : "mt-3"}`}
      >
        <div
          className={cn(
            "flex items-center justify-between p-4 transition-all border rounded-lg",
            isCompleted
              ? "bg-emerald-50 border-emerald-100"
              : "bg-white border-zinc-200 hover:border-emerald-200 hover:bg-emerald-50/30"
          )}
        >
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {isCompleted ? (
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
            ) : (
              <div
                className={cn(
                  "flex items-center justify-center w-5 h-5 rounded-full text-xs font-medium shrink-0",
                  "bg-zinc-100 text-zinc-700"
                )}
              >
                {currentLessonIndexStr}
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <span className={cn("font-medium truncate", "text-zinc-800")}>{lesson.title}</span>
              {lesson.description && <span className="text-sm text-zinc-500 truncate">{lesson.description}</span>}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onLessonClick?.(idx, lesson.id)}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 text-sm font-medium transition-colors rounded-md shrink-0 ml-2",
              isCompleted
                ? "text-white bg-emerald-500 hover:bg-emerald-600"
                : "text-emerald-700 bg-emerald-100 hover:bg-emerald-200"
            )}
          >
            {isCompleted ? "View" : "Start"}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        {lesson.lessons?.length > 0 && (
          <LessonList
            lessons={lesson.lessons}
            depth={depth + 1}
            parentIndexStr={currentLessonIndexStr}
            onLessonClick={onLessonClick}
          />
        )}
      </div>
    );
  };

  // Component for the list of lessons
  const LessonList = ({ lessons, depth = 0, parentIndexStr = "", onLessonClick }) => {
    return (
      <>
        {(lessons || []).map((lesson, idx) => (
          <LessonItem
            key={lesson.id ?? `${moduleId}-lesson-${depth}-${idx}`}
            lesson={lesson}
            idx={idx}
            depth={depth}
            parentIndexStr={parentIndexStr}
            onLessonClick={onLessonClick}
          />
        ))}
      </>
    );
  };

  return (
    // Module Card Container - Mimics styles from [cite: 397, 412]
    <div
      // Removed motion.div
      className="p-6 mb-8 bg-white border border-zinc-200 rounded-xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden"
    >
      {/* Module Header Section - Mimics styles from [cite: 398, 413] */}
      <button
        type="button"
        className="flex items-center gap-2 mb-4 w-full text-left"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-controls={`module-content-${moduleId}`}
      >
        {/* Module Number/Check Icon */}
        <div
          className={cn(
            "flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium transition-all duration-300 shrink-0",
            isModuleCompleted
              ? "bg-emerald-500 text-white hover:bg-emerald-600" // Completed style [cite: 399]
              : "bg-zinc-100 text-zinc-700" // Default style [cite: 413]
          )}
        >
          {isModuleCompleted ? <CheckCircle className="w-4 h-4" /> : index + 1}
        </div>
        {/* Module Title */}
        <h2 className="text-xl font-semibold text-zinc-900 flex-1 truncate" title={module.title}>
          {" "}
          {/* Added flex-1 and truncate */}
          {module.title}
        </h2>
        {/* Completion Badge (Optional, based on UI-update) */}
        {isModuleCompleted && (
          <span className="ml-auto px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-800 rounded-full shrink-0">
            Completed
          </span>
        )}
        {/* Expand/Collapse Chevron (Optional, can be added if needed) */}
        {/* <ChevronRight className={cn("w-5 h-5 transition-transform shrink-0 ml-2", expanded ? "rotate-90 text-emerald-600" : "text-zinc-400")} /> */}
      </button>

      {/* Progress Section - Mimics styles from [cite: 403, 417] */}
      <div className="flex items-center gap-2 mb-4">
        <div className="text-xs text-zinc-500">
          {completedLessons} of {totalLessons} lessons completed
        </div>
        <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Collapsible Lessons Area */}
      {/* Using a simple conditional render instead of AnimatePresence/motion */}
      <div
        id={`module-content-${moduleId}`}
        className={cn(
          "transition-all duration-300 ease-in-out overflow-hidden",
          expanded ? "max-h-[1000px] opacity-100" : "max-h-0 opacity-0" // Basic expand/collapse
        )}
        style={{ transitionProperty: "max-height, opacity" }} // Explicit transitions
      >
        {expanded && (
          <div className="space-y-3">
            {" "}
            {/* Ensure spacing between lessons */}
            <LessonList lessons={module.lessons || []} onLessonClick={onLessonClick} />
          </div>
        )}
      </div>
    </div>
  );
}

export default OutlineItem;
