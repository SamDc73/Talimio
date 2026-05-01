import { useLocation } from "react-router-dom"

import { useSingleProgress } from "@/hooks/use-progress"
import useAppStore from "@/stores/useAppStore"

/**
 * Hook to detect current page context for the learning assistant
 * Returns context data based on the current URL (path-only parsing).
 *
 * Important: This hook intentionally avoids useParams because the
 * ChatSidebar lives outside specific <Route> elements. Parsing the
 * pathname keeps it robust regardless of where the component renders.
 */
export function useCurrentContext() {
	const location = useLocation()

	const pathname = location.pathname || ""
	const segments = pathname.split("/").filter(Boolean)

	let contextType = null
	let contextId = null
	let contextMeta = null

	// videos/:videoId
	if (segments[0] === "videos" && segments[1]) {
		const videoId = segments[1]
		contextType = "video"
		contextId = videoId
	}

	// books/:bookId
	else if (segments[0] === "books" && segments[1]) {
		const bookId = segments[1]
		contextType = "book"
		contextId = bookId
	}

	// course/:courseId or course/preview/:courseId or courses/:courseId
	else if (segments[0] === "course" || segments[0] === "courses") {
		let courseId = null
		let lessonId = null

		if (segments[0] === "course") {
			if (segments[1] === "preview") {
				courseId = segments[2] || null
				// optional nested: course/preview/:courseId/lesson/:lessonId
				if (segments[3] === "lesson" && segments[4]) {
					lessonId = segments[4]
				}
			} else {
				courseId = segments[1] || null
				if (segments[2] === "lesson" && segments[3]) {
					lessonId = segments[3]
				}
			}
		} else if (segments[0] === "courses") {
			courseId = segments[1] || null
			if (segments[2] === "lesson" && segments[3]) {
				lessonId = segments[3]
			}
		}

		if (courseId) {
			contextType = "course"
			contextId = courseId
			contextMeta = { lesson_id: lessonId || null }
		}
	}

	const bookReadingState = useAppStore((state) =>
		contextType === "book" && contextId ? state.books.readingState[contextId] : null
	)
	const progressQuery = useSingleProgress(contextType === "video" ? contextId : null)

	if (contextType === "video") {
		const metadata = progressQuery.metadata || {}
		contextMeta = { timestamp: metadata.position ?? metadata.last_position ?? 0 }
	} else if (contextType === "book") {
		const currentPage = bookReadingState?.currentPage ?? 1
		contextMeta = { page: Math.max(0, Number(currentPage) - 1) }
	}

	if (contextType && contextId) {
		return { contextType, contextId, contextMeta }
	}

	return null
}
