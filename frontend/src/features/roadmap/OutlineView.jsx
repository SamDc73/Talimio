// OutlineView.jsx
// Main entry point for Outline mode: renders all modules using OutlineItem
// Type hints are in comments for clarity

import React, { useState } from "react";
import { LessonViewer } from "../lessons/LessonViewer";
import { useLessonViewer } from "../lessons/useLessonViewer";
import OutlineItem from "./OutlineItem";
import { useOutlineData } from "./useOutlineData";

/**
 * OutlineView renders the full roadmap outline, with all modules and their lessons
 * @param {Object} props
 * @param {string} props.roadmapId - The ID of the roadmap to display.
 * @returns {JSX.Element}
 */
function OutlineView({ roadmapId }) {
  // Accept roadmapId as a prop
  // Get modules data, loading state, and error state from the custom hook
  const { modules, isLoading, error } = useOutlineData(roadmapId);

  // State to track the active lesson
  const [activeLesson, setActiveLesson] = useState(null);

  // Use our lesson viewer hook
  const { lesson, isLoading: lessonLoading, error: lessonError, getOrGenerateLesson, clearLesson } = useLessonViewer();

  // Handler for lesson clicks - now will either view or generate a lesson
  const handleLessonClick = async (moduleIdx, lessonIdx, lessonId) => {
    try {
      // Find the module and lesson
      const module = modules[moduleIdx];
      const lesson = module.lessons[lessonIdx];

      // Set the active lesson
      setActiveLesson({
        moduleId: module.id,
        lessonId: lessonId,
        moduleIdx,
        lessonIdx,
        title: lesson.title,
        description: lesson.description || "",
      });

      // Get or generate the lesson content
      // Make sure we're passing a string for the node ID
      await getOrGenerateLesson(
        String(lessonId), // Convert to string to ensure compatibility
        {
          title: lesson.title,
          description: lesson.description || "",
          skill_level: module.skill_level || "beginner",
        },
      );
    } catch (err) {
      console.error("Error handling lesson click:", err);
    }
  };

  // Handler to go back to the outline view
  const handleBackToOutline = () => {
    setActiveLesson(null);
    clearLesson();
  };

  // Handle loading state
  if (isLoading) {
    return (
      <div
        className="fixed inset-0 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500"
        style={{ marginLeft: 0, paddingTop: "4rem" }}
      >
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500 mb-4" />
        <p>Loading outline...</p>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div
        className="fixed inset-0 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-red-600"
        style={{ marginLeft: 0, paddingTop: "4rem" }}
      >
        <p>Error loading outline: {error}</p>
      </div>
    );
  }

  // Handle empty state
  if (!modules || modules.length === 0) {
    return (
      <div
        className="fixed inset-0 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500"
        style={{ marginLeft: 0, paddingTop: "4rem" }}
      >
        <p>No outline content available for this roadmap.</p>
      </div>
    );
  }

  // TODO: Fetch the actual roadmap title dynamically if available
  const courseTitle = "Roadmap Outline"; // Placeholder title

  // If we have an active lesson, show the lesson viewer
  if (activeLesson && (lesson || lessonLoading)) {
    return <LessonViewer lesson={lesson} isLoading={lessonLoading} error={lessonError} onBack={handleBackToOutline} />;
  }

  // Otherwise, show the outline view
  return (
    <div className="flex-1 p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header Section - Mimicking the style from UI-update.txt */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 mb-1">{courseTitle}</h1>
            {/* Optional: Add a subtitle like in the example */}
            {/* <p className="text-zinc-500 flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                    Building Modern APIs
                </p> */}
          </div>
        </div>

        {/* Render each module using OutlineItem */}
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
