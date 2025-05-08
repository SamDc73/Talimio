import React, { useState } from "react";
import { LessonViewer } from "../../lessons/LessonViewer";
import { useLessonViewer } from "../../lessons/useLessonViewer";
import { useProgress } from "../../../hooks/useProgress";
import OutlineItem from "./OutlineItem";
import { useOutlineData } from "./useOutlineData";

/**
 * OutlineView renders the full roadmap outline, with all modules and their lessons
 * @param {Object} props
 * @param {string} props.roadmapId - The ID of the roadmap to display.
 * @returns {JSX.Element}
 */
function OutlineView({ roadmapId }) {
  const { modules, isLoading, error } = useOutlineData(roadmapId);
  const [activeLesson, setActiveLesson] = useState(null);
  const { lesson, isLoading: lessonLoading, error: lessonError, getOrGenerateLesson, clearLesson } = useLessonViewer();
  const { courseProgress, toggleLessonCompletion, isLessonCompleted } = useProgress(roadmapId);

  const handleLessonClick = async (moduleIdx, lessonIdx, lessonId) => {
    try {
      const module = modules[moduleIdx];
      const lesson = module.lessons[lessonIdx];

      setActiveLesson({
        moduleId: module.id,
        lessonId: lessonId,
        moduleIdx,
        lessonIdx,
        title: lesson.title,
        description: lesson.description || "",
      });

      // Ensure lessonId is a string for compatibility
      await getOrGenerateLesson(String(lessonId), {
        title: lesson.title,
        description: lesson.description || "",
        skill_level: module.skill_level || "beginner",
      });
    } catch (err) {
      console.error("Error handling lesson click:", err);
    }
  };

  const handleBackToOutline = () => {
    setActiveLesson(null);
    clearLesson();
  };

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
  const courseTitle = "Roadmap Outline";

  if (activeLesson && (lesson || lessonLoading)) {
    return <LessonViewer lesson={lesson} isLoading={lessonLoading} error={lessonError} onBack={handleBackToOutline} />;
  }
  return (
    <div className="flex-1 p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 mb-1">{courseTitle}</h1>
          </div>
        </div>

        {modules.map((module, idx) => (
          <OutlineItem
            key={module.id || idx}
            module={module}
            index={idx}
            onLessonClick={(lessonIdx, lessonId) => handleLessonClick(idx, lessonIdx, lessonId)}
            isLessonCompleted={isLessonCompleted}
            toggleLessonCompletion={toggleLessonCompletion}
            courseProgress={courseProgress}
          />
        ))}
      </div>
    </div>
  );
}

export default OutlineView;
