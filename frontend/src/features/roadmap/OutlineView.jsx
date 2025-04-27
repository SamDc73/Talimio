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
  const handleLessonClick = (moduleIdx, lessonIdx) => {
    // For now, just log. You can expand this to navigate, show details, etc.
    // console.log(`Module ${moduleIdx + 1}, Lesson ${lessonIdx + 1} clicked.`);
  };

  // Handle loading state
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto py-10 text-center text-zinc-500">
        Loading outline...
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-10 text-center text-red-600">
        Error loading outline: {error}
      </div>
    );
  }

  // Handle empty state
  if (!modules || modules.length === 0) {
    return (
      <div className="max-w-3xl mx-auto py-10 text-center text-zinc-500">
        No outline content available for this roadmap.
      </div>
    );
  }

  // TODO: Get the actual roadmap title from the data if needed, instead of hardcoding
  const courseTitle = "Roadmap Outline"; // Placeholder, consider fetching title

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8"> {/* Added padding */} 
      <h1 className="text-3xl font-bold mb-8 text-zinc-900">{courseTitle}</h1>
      {/* Render each module as an OutlineItem */}
      {modules.map((module, idx) => (
        <OutlineItem key={module.id} module={module} index={idx} onLessonClick={handleLessonClick} />
      ))}
    </div>
  );
}

export default OutlineView;
