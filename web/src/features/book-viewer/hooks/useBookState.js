import { useEffect, useState } from "react"
import useAppStore from "@/stores/useAppStore"

const EMPTY_READING_STATE = Object.freeze({
	currentPage: 1,
	totalPages: 0,
	zoomLevel: 100,
	scrollPosition: { x: 0, y: 0 },
	epubState: {
		location: null,
		fontSize: 100,
		lastUpdated: null,
	},
	lastUpdated: null,
})

// Book zoom level hook
export const useBookZoomLevel = (bookId) => {
	return useAppStore((state) => state.books.readingState[bookId]?.zoomLevel || 100)
}

// Book current page hook
export const useBookCurrentPage = (bookId) => {
	return useAppStore((state) => state.books.readingState[bookId]?.currentPage || 1)
}

// Book total pages hook
export const useBookTotalPages = (bookId) => {
	return useAppStore((state) => state.books.readingState[bookId]?.totalPages || 0)
}

// Book actions hook
export const useBookActions = () => {
	const updateBookReadingState = useAppStore((state) => state.updateBookReadingState)
	const setBookZoom = useAppStore((state) => state.setBookZoom)
	const setBookProgress = useAppStore((state) => state.setBookProgress)
	const toggleBookItem = useAppStore((state) => state.toggleBookItem)
	const batchUpdateBook = useAppStore((state) => state.batchUpdateBook)
	const setBookLoading = useAppStore((state) => state.setBookLoading)
	const setBookError = useAppStore((state) => state.setBookError)

	// EPUB-specific actions
	const onEpubLocationChange = useAppStore((state) => state.onEpubLocationChange)
	const updateEpubFontSize = useAppStore((state) => state.updateEpubFontSize)
	const getEpubState = useAppStore((state) => state.getEpubState)

	return {
		updateBookReadingState,
		setBookZoom,
		setBookProgress,
		toggleBookItem,
		batchUpdateBook,
		setBookLoading,
		setBookError,
		// EPUB-specific actions
		onEpubLocationChange,
		updateEpubFontSize,
		getEpubState,
	}
}

// Sidebar open state hook
export const useSidebarOpen = () => {
	return useAppStore((state) => state.preferences?.sidebarOpen ?? true)
}

// Toggle sidebar hook
export const useToggleSidebar = () => {
	return useAppStore((state) => state.toggleSidebar)
}
// Book reading state hook
export const useBookReadingState = (bookId) => {
	return useAppStore((state) => state.books.readingState[bookId] || EMPTY_READING_STATE)
}

// Book progress hook
export const useBookProgress = (bookId) => {
	return useAppStore((state) => state.books.progress[bookId] || null)
}

// Book loading state hook
export const useBookLoading = (bookId) => {
	return useAppStore((state) => state.books.loading[bookId] || false)
}

// Book error state hook
export const useBookError = (bookId) => {
	return useAppStore((state) => state.books.error[bookId] || null)
}

export const useBookStoreHydrated = () => {
	const [hydrated, setHydrated] = useState(() => useAppStore.persist?.hasHydrated?.() ?? false)

	useEffect(() => {
		if (useAppStore.persist?.hasHydrated?.()) {
			setHydrated(true)
			return
		}

		const unsub = useAppStore.persist?.onFinishHydration?.(() => {
			setHydrated(true)
		})

		return () => {
			unsub?.()
		}
	}, [])

	return hydrated
}
