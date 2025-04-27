// OutlineView.jsx
// Main entry point for Outline mode: renders all modules using OutlineItem
// Type hints are in comments for clarity

import React from "react";
import { useOutlineData } from "./useOutlineData";
import OutlineItem from "./OutlineItem";

/**
 * OutlineView renders the full roadmap outline, with all modules and their lessons
 * @param {Object} props
 * @param {string} props.roadmapId - The ID of the roadmap to display.
 * @returns {JSX.Element}
 */
function OutlineView({ roadmapId }) { // Accept roadmapId as a prop
  // Get modules data, loading state, and error state from the custom hook
  const { modules, isLoading, error } = useOutlineData(roadmapId);

  // Handler for lesson clicks (optional, can be expanded)
  const handleLessonClick = (moduleIdx, lessonIdx, lessonId) => {
    // For now, just log. You can expand this to navigate, show details, etc.
    // console.log(`Module ${moduleIdx + 1}, Lesson ${lessonIdx + 1} (ID: ${lessonId}) clicked.`);
    // Potentially navigate to a lesson view here, passing module/lesson IDs
  };

  // Handle loading state
  if (isLoading) {
    return (
      // Use a similar loading style
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500">
        Loading outline...
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] text-red-600">
        Error loading outline: {error}
      </div>
    );
  }

  // Handle empty state
  if (!modules || modules.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500">
        No outline content available for this roadmap.
      </div>
    );
  }

  // TODO: Fetch the actual roadmap title dynamically if available
  const courseTitle = "Roadmap Outline"; // Placeholder title

  return (
    <div className="flex-1 p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header Section - Mimicking the style from UI-update.txt */}
        <div className="flex items-center justify-between mb-8">
            <div> {/* Removed motion.div as framer-motion isn't explicitly included */}
                <h1 className="text-2xl font-bold text-zinc-900 mb-1">{courseTitle}</h1>
                {/* Optional: Add a subtitle like in the example */}
                {/* <p className="text-zinc-500 flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                    Building Modern APIs
                </p> */}
            </div>
        </div>

        {/* Render each module using OutlineItem */}
        {/* The wrapping div is implicitly handled by mapping over modules */}
        {modules.map((module, idx) => (
          <OutlineItem
            key={module.id || idx}
            module={module}
            index={idx}
            onLessonClick={(lessonIdx, lessonId) => handleLessonClick(idx, lessonIdx, lessonId)}
          />
        ))}
      </div>
    </div>
  );
}

export default OutlineView;
