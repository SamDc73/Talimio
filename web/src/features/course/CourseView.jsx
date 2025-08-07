import { useParams } from "react-router-dom"
import DocumentsView from "./views/DocumentsView"
import LessonView from "./views/LessonView"
import OutlineView from "./views/outline"
import TrackView from "./views/track"

/**
 * Simple course view component that renders ONLY the content,
 * no header or sidebar (those are rendered at App level).
 */
export default function SimpleCourseView({ mode, modules, roadmapId }) {
	const { lessonId } = useParams()

	// If viewing a lesson, show lesson view
	if (lessonId) {
		return <LessonView courseId={roadmapId} lessonId={lessonId} />
	}

	// Otherwise show course overview based on mode
	switch (mode) {
		case "outline":
			return <OutlineView roadmapId={roadmapId} modules={modules} />
		case "track":
			return <TrackView roadmapId={roadmapId} modules={modules} />
		case "documents":
			return <DocumentsView courseId={roadmapId} />
		default:
			return <OutlineView roadmapId={roadmapId} modules={modules} />
	}
}
