// Course feature exports

export * from "./api/compatibilityApi"
export * from "./api/courseApi"
// Course API
export { fetchLesson, fetchLessons, generateLesson } from "./api/lessonsApi"
// Progress updates flow through the shared hooks/useProgress infrastructure; feature wrapper removed
export { default as CoursePage } from "./CoursePage"
export { ContentRenderer } from "./components/ContentRenderer"
// Course components
export { LessonViewer } from "./components/LessonViewer"
export { MDXRenderer } from "./components/MDXRenderer"
export { default as OutlineNode } from "./components/navigation/OutlineNode"
export { useCourseData } from "./hooks/useCourseData"
// Course hooks
export { useLessonViewer } from "./hooks/useLessonViewer"
export { useOutlineData } from "./hooks/useOutlineData"
export { useRoadmapData } from "./hooks/useRoadmapData"
export { useTrackData } from "./hooks/useTrackData"

// Course Views
export { default as CourseLayout } from "./views/CourseLayout"
export { default as OutlineView } from "./views/outline/index"
export { default as TrackView } from "./views/track/index"
