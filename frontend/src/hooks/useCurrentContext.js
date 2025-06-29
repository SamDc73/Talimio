import { useMemo } from "react";
import { useLocation, useParams } from "react-router-dom";
import useAppStore from "../stores/useAppStore";

/**
 * Hook to detect current page context for the learning assistant
 * Returns context data based on the current route and page state
 */
export function useCurrentContext() {
	const location = useLocation();
	const params = useParams();
	const getVideoProgress = useAppStore((state) => state.getVideoProgress);
	const getBookProgress = useAppStore((state) => state.getBookProgress);

	const context = useMemo(() => {
		const pathname = location.pathname;

		// Video context: /videos/:videoId
		if (pathname.startsWith("/videos/") && params.videoId) {
			const videoProgress = getVideoProgress(params.videoId);
			const currentTime = videoProgress?.currentTime || 0;

			return {
				contextType: "video",
				contextId: params.videoId,
				contextMeta: {
					timestamp: currentTime,
				},
			};
		}

		// Book context: /books/:bookId
		if (pathname.startsWith("/books/") && params.bookId) {
			const bookProgress = getBookProgress(params.bookId);
			const currentPage = bookProgress?.currentPage || 1;

			return {
				contextType: "book",
				contextId: params.bookId,
				contextMeta: {
					page: currentPage - 1, // Convert to 0-based indexing for backend
				},
			};
		}

		// Course context: /courses/:courseId
		if (pathname.startsWith("/courses/") && params.courseId) {
			// For courses, we need the current lesson ID
			// This might need to be extracted from the URL or passed down
			// For now, we'll check if there's a lessonId in params
			return {
				contextType: "course",
				contextId: params.courseId,
				contextMeta: {
					lesson_id: params.lessonId || null,
				},
			};
		}

		// No context (general pages)
		return null;
	}, [location.pathname, params, getVideoProgress, getBookProgress]);

	return context;
}
