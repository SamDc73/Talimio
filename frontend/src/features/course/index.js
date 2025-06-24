// Course feature exports
export { default as CoursePage } from "./CoursePage";

// Course components
export { LessonViewer } from "./components/LessonViewer";
export { ContentRenderer } from "./components/ContentRenderer";
export { MDXRenderer } from "./components/MDXRenderer";
export { default as OutlineNode } from "./components/navigation/OutlineNode";

// Course hooks
export { useLessonViewer } from "./hooks/useLessonViewer";
export { useOutlineData } from "./hooks/useOutlineData";
export { useRoadmapData } from "./hooks/useRoadmapData";
export { useRoadmapState } from "./hooks/useRoadmapState";
export { useTrackData } from "./hooks/useTrackData";

// Course API
export { fetchLesson, fetchLessons, generateLesson } from "./api/lessonsApi";
export * from "./api/courseApi";
export * from "./api/progressApi";
export * from "./api/compatibilityApi";

// Course Views
export { default as CourseLayout } from "./views/CourseLayout";
export { default as OutlineView } from "./views/outline/index";
export { default as TrackView } from "./views/track/index";