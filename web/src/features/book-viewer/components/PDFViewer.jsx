/**
 * PDF Highlighter component that adds highlighting functionality on top of PDFViewer.
 * Manages highlight creation, deletion, and interaction while composing the core PDFViewer.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { debounce } from "lodash-es"
import { Highlighter, Sparkles } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Highlight, PdfHighlighter, PdfLoader } from "react-pdf-highlighter"
import { supabase } from "@/lib/supabase"
import { highlightService } from "@/services/highlightService"
import { useHighlightActions } from "@/stores/highlights"
import useAppStore from "@/stores/useAppStore"

import "react-pdf-highlighter/dist/style.css"
import "../styles/highlights.css" // Apply unified highlight overrides
import "../styles/pdf-viewer.css" // PDF viewer specific styles

/**
 * PDFViewer - PDF viewer component with highlighting capabilities
 *
 * @param {Object} props
 * @param {string} props.url - URL of the PDF to load
 * @param {Function} props.onTextSelection - Callback when text is selected for AI
 * @param {string} props.bookId - ID of the book for state management
 * @param {Function} props.registerApi - Function to register viewer API (deprecated)
 */
function PDFViewer({ url, onTextSelection, bookId, registerApi = null }) {
	// State for PDF URL resolution
	const [pdfUrl, setPdfUrl] = useState(null)
	const [loading, setLoading] = useState(true)
	const [loadError, setLoadError] = useState(null)

	// Refs for scroll management
	const scrollToRef = useRef(null)
	const pdfDocumentRef = useRef(null)
	const pdfHighlighterRef = useRef(null)
	const hasRestoredPageRef = useRef(false)

	// Highlight store actions
	const { onHighlightClick, onHighlightHover } = useHighlightActions()

	// Reading state from store
	const updateBookReadingState = useAppStore((state) => state.updateBookReadingState)
	const getBookReadingState = useAppStore((state) => state.getBookReadingState)

	// Zoom state
	const [scale, setScale] = useState(1.0)

	// Query client for cache management
	const queryClient = useQueryClient()

	// Fetch highlights from server
	const { data: highlights = [], isLoading: highlightsLoading } = useQuery({
		queryKey: ["highlights", "book", bookId],
		queryFn: async () => {
			try {
				const data = await highlightService.getHighlights("book", bookId)
				return data
			} catch (error) {
				// Silently handle auth errors - user might not be logged in
				if (error?.status === 401 || error?.status === 422) {
					return []
				}
				throw error
			}
		},
		enabled: !!bookId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		gcTime: 10 * 60 * 1000, // 10 minutes cache
		retry: false, // Don't retry on auth errors
	})

	// Create highlight mutation with optimistic updates
	const createHighlightMutation = useMutation({
		mutationFn: async ({ position, content, comment }) => {
			// Validate required data
			if (!position?.rects || !Array.isArray(position.rects)) {
				throw new Error("Invalid highlight position data")
			}

			if (!bookId) {
				throw new Error("Cannot create highlight without book ID")
			}

			// Transform position data to match backend expectations
			const transformedRects = position.rects.map((rect) => ({
				x1: rect.x1,
				y1: rect.y1,
				x2: rect.x2,
				y2: rect.y2,
				width: rect.width,
				height: rect.height,
				pageNumber: rect.pageNumber || position.pageNumber,
			}))

			// Format data for backend PDF validation
			const highlightData = {
				text: content?.text || "",
				page: position.pageNumber,
				position: {
					rects: transformedRects,
					pageNumber: position.pageNumber,
					boundingRect: position.boundingRect,
				},
				note: comment?.text || "", // Store comment text as 'note' field
			}
			const result = await highlightService.createHighlight("book", bookId, highlightData)
			return result
		},
		onMutate: async ({ position, content, comment }) => {
			// Cancel any outgoing refetches (so they don't overwrite our optimistic update)
			await queryClient.cancelQueries({ queryKey: ["highlights", "book", bookId] })

			// Snapshot the previous value
			const previousHighlights = queryClient.getQueryData(["highlights", "book", bookId])

			// Optimistically update to the new value
			queryClient.setQueryData(["highlights", "book", bookId], (old) => [
				...(old || []),
				{
					id: `temp-${Date.now()}`,
					position,
					content,
					comment,
					type: "BOOK",
					entityId: bookId,
					userId: supabase.auth.user()?.id,
					createdAt: new Date().toISOString(),
					updatedAt: new Date().toISOString(),
				},
			])

			// Return a context object with the snapshotted value
			return { previousHighlights }
		},
		onError: (_error, _variables, context) => {
			// Rollback to the previous value on error
			queryClient.setQueryData(["highlights", "book", bookId], context.previousHighlights)
		},
		onSuccess: (_data) => {
			// Invalidate and refetch
			queryClient.invalidateQueries({ queryKey: ["highlights", "book", bookId] })
		},
	})

	// Map server highlights to PDFHighlighter format
	const pdfHighlights = useMemo(() => {
		return highlights.map((h) => ({
			...h,
			comment: { text: h.note || "" },
		}))
	}, [highlights])

	const handleHighlightAI = (highlight) => {
		onTextSelection(highlight)
	}

	// Tip component for text selection
	function CreateTipContent({ position, content, hideTipAndSelection }) {
		const handleCreateHighlight = (note) => {
			const newHighlight = {
				position,
				content,
				comment: { text: note },
			}
			createHighlightMutation.mutate(newHighlight)
			hideTipAndSelection()
		}

		const handleAIAction = () => {
			handleHighlightAI({ content, position })
			hideTipAndSelection()
		}

		const handleHighlightClick = () => {
			handleCreateHighlight("")
		}

		return (
			<div className="flex flex-col space-y-2 p-2 bg-white rounded-lg shadow-lg border border-gray-200">
				<button
					type="button"
					onClick={handleHighlightClick}
					className="flex items-center px-3 py-1 text-sm text-gray-700 hover:bg-gray-100 rounded"
				>
					<Highlighter className="w-4 h-4 mr-2" />
					Highlight
				</button>
				<button
					type="button"
					onClick={handleAIAction}
					className="flex items-center px-3 py-1 text-sm text-gray-700 hover:bg-gray-100 rounded"
				>
					<Sparkles className="w-4 h-4 mr-2" />
					Ask AI
				</button>
			</div>
		)
	}

	const zoomIn = useCallback(() => {
		setScale((prevScale) => {
			const currentScale = typeof prevScale === "number" ? prevScale : 1.0
			return Math.min(currentScale + 0.2, 3.0)
		})
	}, [])

	const zoomOut = useCallback(() => {
		setScale((prevScale) => {
			const currentScale = typeof prevScale === "number" ? prevScale : 1.0
			return Math.max(currentScale - 0.2, 0.4)
		})
	}, [])

	// Create debounced function using useMemo to ensure stable reference
	const trackCurrentPage = useMemo(
		() =>
			debounce((viewer) => {
				if (!viewer) return
				const { currentPage } = viewer
				const readingState = getBookReadingState(bookId)
				if (readingState?.currentPage !== currentPage) {
					updateBookReadingState(bookId, { currentPage })
				}
			}, 500),
		[bookId, getBookReadingState, updateBookReadingState]
	)

	const handlePdfLoad = (pdfDocument) => {
		pdfDocumentRef.current = pdfDocument

		// Restore last known page
		const readingState = getBookReadingState(bookId)
		if (readingState?.currentPage && !hasRestoredPageRef.current) {
			const tempHighlight = {
				id: `goto-page-${readingState.currentPage}`,
				position: { pageNumber: readingState.currentPage },
			}
			if (scrollToRef.current) {
				scrollToRef.current(tempHighlight)
			}
			hasRestoredPageRef.current = true
		}
	}

	// Register API for parent component
	useEffect(() => {
		if (registerApi) {
			const fitToScreen = () => {
				setScale("page-width")
			}

			const goToPage = (pageNumber) => {
				if (scrollToRef.current) {
					const tempHighlight = { id: `goto-page-${pageNumber}`, position: { pageNumber } }
					scrollToRef.current(tempHighlight)
				}
			}

			const getCurrentPage = () => {
				const state = getBookReadingState(bookId)
				return state?.currentPage || 1
			}

			const getTotalPages = () => {
				return pdfDocumentRef.current?.numPages || 0
			}

			registerApi({
				goToPage,
				fitToScreen,
				getCurrentPage,
				getTotalPages,
				zoomIn,
				zoomOut,
			})
		}
	}, [bookId, registerApi, getBookReadingState, zoomIn, zoomOut])

	// Handle API redirects to get actual PDF URL
	useEffect(() => {
		// Reset state when URL changes
		pdfDocumentRef.current = null
		hasRestoredPageRef.current = false

		if (!url) {
			setPdfUrl(null)
			return
		}
		setLoading(true)
		setLoadError(null)

		if (url.startsWith("/api")) {
			// Handle API URLs that need authentication
			supabase.auth
				.getSession()
				.then(({ data: { session } }) => {
					const headers = {}
					if (session?.access_token) {
						headers.Authorization = `Bearer ${session.access_token}`
					}

					return fetch(url, {
						method: "GET",
						headers,
						credentials: "include",
					})
				})
				.then(async (response) => {
					if (response.ok) {
						const contentType = response.headers.get("content-type")
						if (contentType?.includes("application/json")) {
							const data = await response.json()
							if (data.url && data.type === "presigned") {
								setPdfUrl(data.url)
							}
						} else if (contentType?.includes("application/pdf")) {
							setPdfUrl(url)
						}
					} else {
						throw new Error(`Failed to fetch PDF: ${response.status}`)
					}
					setLoading(false)
					return null
				})
				.catch((error) => {
					setLoadError(error.message)
					setLoading(false)
				})
		} else {
			setPdfUrl(url)
			setLoading(false)
		}
	}, [url])

	// Error states
	if (!url) {
		return (
			<div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg">
				<p className="text-gray-600">No PDF URL provided</p>
			</div>
		)
	}

	if (loading && !pdfUrl) {
		return (
			<div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg">
				<div className="text-center">
					<p className="text-gray-600">Resolving PDF location...</p>
					<p className="text-xs text-gray-500 mt-2">Fetching document from server</p>
				</div>
			</div>
		)
	}

	if (!pdfUrl && loadError) {
		return (
			<div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg">
				<div className="text-center">
					<p className="text-red-600">Failed to load PDF</p>
					<p className="text-xs text-red-500 mt-2">{loadError}</p>
				</div>
			</div>
		)
	}

	if (!pdfUrl) {
		return null
	}

	return (
		<div className="pdf-viewer-wrapper h-full">
			<PdfLoader
				url={pdfUrl}
				beforeLoad={<div className="flex items-center justify-center h-64 text-gray-600">Loading PDF…</div>}
				onError={(error) => {
					setLoadError(error.message || "Failed to load PDF")
				}}
			>
				{(pdfDocument) => {
					// Handle PDF load once
					if (!pdfDocumentRef.current) {
						handlePdfLoad(pdfDocument)
					}

					return (
						<PdfHighlighter
							ref={pdfHighlighterRef}
							pdfDocument={pdfDocument}
							scale={scale}
							highlights={pdfHighlights}
							onScrollChange={() => {
								trackCurrentPage(pdfHighlighterRef.current?.viewer)
							}}
							scrollRef={(scrollTo) => {
								scrollToRef.current = scrollTo
							}}
							enableAreaSelection={(event) => event.altKey}
							onSelectionFinished={(position, content, hideTipAndSelection) => {
								return (
									<CreateTipContent position={position} content={content} hideTipAndSelection={hideTipAndSelection} />
								)
							}}
							highlightTransform={(
								highlight,
								_index,
								_setTip,
								_hideTip,
								_viewportToScaled,
								_screenshot,
								isScrolledTo
							) => (
								<Highlight
									isScrolledTo={isScrolledTo}
									position={highlight.position}
									comment={highlight.comment}
									onClick={() => onHighlightClick(highlight.id)}
									onMouseOver={() => onHighlightHover(highlight.id)}
								/>
							)}
						>
							{/* Empty div for PdfHighlighter's internal structure */}
							<div className="absolute inset-0 pointer-events-none" />
							{highlightsLoading && (
								<div className="absolute top-2 left-2 z-10 rounded bg-black/50 text-white text-xs px-2 py-1">
									Loading highlights...
								</div>
							)}
						</PdfHighlighter>
					)
				}}
			</PdfLoader>
		</div>
	)
}

export default PDFViewer
