import { useEffect, useRef, useState } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import { supabase } from "@/lib/supabase"
import useAppStore from "@/stores/useAppStore"
import "./PDFViewer.css"

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

const DOCUMENT_OPTIONS = Object.freeze({
	disableStream: true,
	disableAutoFetch: true,
})

const DEBUG_PDF = import.meta.env?.VITE_DEBUG_PDF === "true"
const dlog = (..._args) => {
	if (DEBUG_PDF) {
	}
}

function LazyPDFViewer({ url, zoom = 100, onTextSelection, bookId }) {
	const [numPages, setNumPages] = useState(null)
	const [visiblePages, setVisiblePages] = useState(new Set([1, 2, 3]))
	const [loadError, setLoadError] = useState(null)
	const [loading, setLoading] = useState(true)
	const [pdfUrl, setPdfUrl] = useState(null)
	const [file, setFile] = useState(null)

	// Get stored reading state - use specific selectors to avoid re-renders
	const storedPage = useAppStore((state) => state.books.readingState?.[bookId]?.currentPage)
	const updateBookReadingState = useAppStore((state) => state.updateBookReadingState)

	// Calculate scale from zoom percentage
	const scale = zoom / 100

	// Ref to track the viewer container for scroll position maintenance
	const viewerContainerRef = useRef(null)

	// Handle text selection for tooltips
	const handleTextSelection = () => {
		const selection = window.getSelection()
		const selectedText = selection.toString().trim()

		if (selectedText && onTextSelection) {
			// Get selection bounds for tooltip positioning
			const range = selection.getRangeAt(0)
			const rect = range.getBoundingClientRect()

			onTextSelection({
				text: selectedText,
				bounds: {
					x: rect.x,
					y: rect.y,
					width: rect.width,
					height: rect.height,
				},
			})

			dlog("📝 Text selected:", `${selectedText.substring(0, 50)}...`)
		}
	}

	// Handle API redirects to get actual PDF URL
	const resolvedForUrlRef = useRef(null)
	const inFlightRunRef = useRef(0)
	useEffect(() => {
		if (!url) {
			setPdfUrl(null)
			return
		}

		dlog("Processing URL")
		setLoading(true)
		setLoadError(null)
		setNumPages(null)
		setVisiblePages(new Set([1, 2, 3]))

		if (url.startsWith("/api")) {
			if (resolvedForUrlRef.current === url && pdfUrl) {
				dlog("Skipping duplicate")
				setLoading(false)
				return
			}
			dlog("Fetching PDF from API")

			const runId = ++inFlightRunRef.current
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
					// Ignore stale responses from previous runs
					if (runId !== inFlightRunRef.current) return null
					dlog("API response:", response.status)

					if (response.ok) {
						const contentType = response.headers.get("content-type")
						if (contentType?.includes("application/json")) {
							const data = await response.json()
							dlog("Got JSON response")
							if (data.url && data.type === "presigned") {
								dlog("Using presigned URL")
								setPdfUrl((prev) => prev || data.url) // only set once
								resolvedForUrlRef.current = url
							} else {
								throw new Error("Invalid JSON response format")
							}
						} else if (contentType?.includes("application/pdf")) {
							dlog("Got PDF response")
							setPdfUrl((prev) => prev || url)
							resolvedForUrlRef.current = url
						} else {
							const _text = await response.text()
							if (DEBUG_PDF) throw new Error("Server returned unexpected content type")
						}
						setLoading(false)
					} else {
						let errorMsg = `Failed to fetch PDF: ${response.status} ${response.statusText}`
						try {
							const errorData = await response.json()
							if (errorData.detail) {
								errorMsg = errorData.detail
							}
						} catch {}
						throw new Error(errorMsg)
					}
					return null
				})
				.catch((error) => {
					if (runId !== inFlightRunRef.current) return
					setLoadError(error.message)
					setLoading(false)
				})
		} else {
			dlog("Using direct URL")
			setPdfUrl(url)
		}

		const currentRunId = inFlightRunRef.current
		return () => {
			dlog("Cleanup")
			if (currentRunId !== undefined) {
				inFlightRunRef.current = currentRunId + 1
			}
		}
	}, [url, pdfUrl])

	// Create file object from resolved PDF URL
	// This ensures the file object reference is stable across re-renders
	useEffect(() => {
		if (pdfUrl) {
			const isPresignedUrl =
				pdfUrl.includes("cloudflarestorage.com") || pdfUrl.includes("X-Amz-") || pdfUrl.includes("amazonaws.com")

			setFile({
				url: pdfUrl,
				// NEVER use credentials for presigned URLs (causes CORS errors)
				// Only use credentials for our local API endpoints
				withCredentials: pdfUrl.startsWith("/api") && !isPresignedUrl,
			})

			dlog("PDF file ready")
		} else {
			setFile(null)
		}
	}, [pdfUrl])

	const onDocumentLoadSuccess = (pdf) => {
		dlog("PDF details:", { pages: pdf.numPages })
		setNumPages(pdf.numPages)
		setLoadError(null)
		setLoading(false)

		// Immediately update total pages in store for UI
		if (updateBookReadingState && bookId) {
			updateBookReadingState(
				bookId,
				{
					totalPages: pdf.numPages,
					currentPage: storedPage || 1,
				},
				true
			) // Skip API sync for immediate update
		}
		if (storedPage && storedPage <= pdf.numPages && storedPage > 0) {
			const savedPage = storedPage
			// Set visible pages around the saved page
			setVisiblePages(new Set([Math.max(1, savedPage - 1), savedPage, Math.min(pdf.numPages, savedPage + 1)]))

			// Scroll to the saved page after a short delay to allow rendering
			setTimeout(() => {
				const pageElement = document.querySelector(`[data-page="${savedPage}"]`)
				if (pageElement) {
					pageElement.scrollIntoView({ behavior: "instant", block: "start" })
					// Mark as initialized immediately after scrolling to correct page
					// This prevents incorrect pages from being saved during initialization
					setTimeout(() => {
						isInitializedRef.current = true
						dlog(`Initialized at page ${savedPage}`)
					}, 100) // Small delay to ensure scroll completes
				} else {
					isInitializedRef.current = true
				}
			}, 300) // Reduced delay for faster restoration
		} else {
			setTimeout(() => {
				isInitializedRef.current = true
				dlog("Initialized at page 1 (no saved page)")
			}, 300)
		}
	}

	const onDocumentLoadError = (error) => {
		// Only log errors in debug mode
		dlog("PDF load error:", error.message)

		// Check if it's a CORS error
		if (error.message?.includes("NetworkError") || error.message?.includes("CORS")) {
			dlog("CORS error detected")
			setLoadError("Unable to load PDF due to CORS restrictions. Please contact support.")
		} else if (error.message?.includes("Error in input stream")) {
			dlog("Invalid PDF data received")
			setLoadError(
				"Invalid PDF data received from server. The file might be corrupted or the server returned an error page."
			)
		} else {
			setLoadError(error.message || "Failed to load PDF")
		}
		setLoading(false)
	}

	const onSourceError = (error) => {
		dlog("Source error:", error)
		setLoadError("Failed to fetch PDF from server. Please check your connection and try again.")
		setLoading(false)
	}

	// Debounce timer for saving page state
	const saveTimerRef = useRef(null)

	// Track if PDF has been initialized to prevent saving during initial load
	const isInitializedRef = useRef(false)
	// Track the most visible page to avoid incorrect saves
	const visiblePagesMapRef = useRef(new Map())
	// Track the current most visible page to avoid redundant updates
	const currentMostVisiblePageRef = useRef(null)
	// Store the observer instance globally to share between all pages
	const pageObserverRef = useRef(null)
	// Track which nodes are being observed for cleanup
	const observedNodesRef = useRef(new Set())

	// Track last scale to detect changes
	const lastScaleRef = useRef(scale)

	// Maintain scroll position during zoom changes
	useEffect(() => {
		if (!viewerContainerRef.current || lastScaleRef.current === scale) return

		const container = viewerContainerRef.current
		const wrapper = container.querySelector(".pdf-viewer-wrapper")
		if (!wrapper) return

		// Store current viewport center before zoom
		const viewportHeight = container.clientHeight
		const scrollTop = container.scrollTop
		const currentCenter = scrollTop + viewportHeight / 2

		// Calculate the ratio of where we are in the document
		const oldScrollHeight = wrapper.scrollHeight
		const scrollRatio = currentCenter / oldScrollHeight

		// Let the DOM update with new scale
		requestAnimationFrame(() => {
			// Calculate new position to maintain the same center
			const newScrollHeight = wrapper.scrollHeight
			const newCenter = scrollRatio * newScrollHeight
			const newScrollTop = newCenter - viewportHeight / 2

			// Apply the new scroll position
			container.scrollTop = Math.max(0, newScrollTop)

			// Update the last scale reference
			lastScaleRef.current = scale
		})
	}, [scale])

	// Create a single IntersectionObserver for all pages
	// Recreate only when numPages changes (not on every zoom)
	useEffect(() => {
		// Save current page to store with debouncing - moved inside useEffect
		const saveCurrentPage = (pageNum) => {
			if (!bookId || !numPages || pageNum < 1) return

			// Update store immediately for instant UI updates
			if (updateBookReadingState) {
				updateBookReadingState(
					bookId,
					{
						currentPage: pageNum,
						totalPages: numPages,
					},
					true
				) // Skip API sync for immediate update
				dlog(`💾 Updated page ${pageNum} (instant)`)
			}

			// Clear existing timer for API sync
			if (saveTimerRef.current) {
				clearTimeout(saveTimerRef.current)
			}

			// Sync to API after 1 second of no page changes
			saveTimerRef.current = setTimeout(() => {
				if (updateBookReadingState) {
					updateBookReadingState(
						bookId,
						{
							currentPage: pageNum,
							totalPages: numPages,
						},
						false
					) // Include API sync
					dlog(`💾 Synced page ${pageNum} to API`)
				}
			}, 1000)
		}

		// Store the observed nodes set in a local variable for cleanup
		const observedNodes = observedNodesRef.current

		// Create the observer
		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					// Extract page number from data attribute
					const pageNum = parseInt(entry.target.dataset.pageNumber)
					if (Number.isNaN(pageNum)) return

					if (entry.isIntersecting) {
						// Track visibility ratio of each page
						visiblePagesMapRef.current.set(pageNum, entry.intersectionRatio)

						// Only update current page after initialization
						if (isInitializedRef.current) {
							// Find the most visible page (no threshold needed!)
							let maxRatio = 0
							let mostVisiblePage = null
							visiblePagesMapRef.current.forEach((ratio, num) => {
								if (ratio > maxRatio) {
									maxRatio = ratio
									mostVisiblePage = num
								}
							})

							// Only save if the most visible page has changed
							// This prevents redundant updates on every scroll event
							if (mostVisiblePage && mostVisiblePage !== currentMostVisiblePageRef.current) {
								currentMostVisiblePageRef.current = mostVisiblePage
								saveCurrentPage(mostVisiblePage)
							}
						}

						setVisiblePages((prev) => {
							const newSet = new Set(prev)
							newSet.add(pageNum)
							// Pre-load adjacent pages
							if (pageNum > 1) newSet.add(pageNum - 1)
							if (pageNum < numPages) newSet.add(pageNum + 1)

							// Remove excessive logging - only log in debug mode for milestones
							if (DEBUG_PDF && (pageNum === 1 || pageNum % 10 === 0 || pageNum === numPages)) {
								dlog(`Page ${pageNum} visible`)
							}
							return newSet
						})
					} else {
						// Remove from visibility tracking when not intersecting
						visiblePagesMapRef.current.delete(pageNum)
					}
				})
			},
			{
				rootMargin: "500px", // Increased margin for smoother loading
				threshold: [0, 0.25, 0.5, 0.75, 1.0], // Multiple thresholds for better precision
			}
		)

		// Store the observer in ref
		pageObserverRef.current = observer

		// Re-observe any existing page elements that were rendered before observer was ready
		setTimeout(() => {
			const pageElements = document.querySelectorAll("[data-page]")
			pageElements.forEach((element) => {
				const pageNum = parseInt(element.dataset.page)
				if (!Number.isNaN(pageNum) && !observedNodes.has(element)) {
					element.dataset.pageNumber = pageNum // Add the pageNumber attribute for observer
					observer.observe(element)
					observedNodes.add(element)
				}
			})
		}, 100) // Small delay to ensure elements are in DOM

		// Cleanup function
		return () => {
			if (observer) {
				observer.disconnect()
			}
			// Use the captured observedNodes variable to avoid stale closure issues
			if (observedNodes) {
				observedNodes.clear()
			}
			pageObserverRef.current = null
		}
	}, [numPages, bookId, updateBookReadingState]) // Recreate observer only when numPages, bookId or updateBookReadingState changes

	// Intersection observer for lazy loading pages
	const pageRef = (node, pageNum) => {
		if (!node) {
			// Node is being unmounted, clean up
			return
		}

		// Store page number as data attribute for the observer
		node.dataset.pageNumber = pageNum

		// Use the shared observer instance
		if (pageObserverRef.current && !observedNodesRef.current.has(node)) {
			pageObserverRef.current.observe(node)
			observedNodesRef.current.add(node)
		}
	}

	// The file object is now created in a useEffect hook to avoid re-renders
	// and to ensure the reference is stable.

	if (!url) {
		return (
			<div className="pdf-error">
				<p>No PDF URL provided</p>
			</div>
		)
	}

	if (loading && !pdfUrl) {
		return (
			<div className="pdf-loading">
				<p>Resolving PDF location...</p>
				<p style={{ fontSize: "12px", color: "#666", marginTop: "8px" }}>Fetching document from server</p>
			</div>
		)
	}

	if (!pdfUrl && loadError) {
		return (
			<div className="pdf-error">
				<p>Failed to load PDF</p>
				<p style={{ fontSize: "12px", color: "#d32f2f", marginTop: "8px" }}>{loadError}</p>
			</div>
		)
	}

	return (
		<div className="pdf-viewer-container" ref={viewerContainerRef} onMouseUp={handleTextSelection} role="document">
			<div className="pdf-viewer-wrapper">
				<Document
					key={pdfUrl || "doc"}
					file={file}
					options={DOCUMENT_OPTIONS}
					onLoadSuccess={onDocumentLoadSuccess}
					onLoadError={onDocumentLoadError}
					onSourceError={onSourceError}
					loading={
						<div className="pdf-loading">
							<p>Loading PDF...</p>
							<p style={{ fontSize: "12px", color: "#666", marginTop: "8px" }}>
								PDF.js v{pdfjs.version} (Worker bundled locally)
							</p>
						</div>
					}
					error={
						<div className="pdf-error">
							<p>Failed to load PDF</p>
							{loadError && (
								<>
									<p
										style={{
											fontSize: "12px",
											color: "#d32f2f",
											marginTop: "8px",
										}}
									>
										{loadError}
									</p>
									{loadError.includes("CORS") && (
										<p
											style={{
												fontSize: "11px",
												color: "#666",
												marginTop: "8px",
											}}
										>
											The PDF is hosted on a different domain that doesn't allow direct access.
										</p>
									)}
								</>
							)}
							<p style={{ fontSize: "11px", color: "#666", marginTop: "8px" }}>
								Check browser console for technical details
							</p>
						</div>
					}
				>
					{numPages &&
						Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
							<div
								key={`page-${pageNum}`}
								className="pdf-page-wrapper"
								data-page={pageNum}
								ref={(node) => pageRef(node, pageNum)}
								style={{
									minHeight: `${800 * scale}px`,
									display: "flex",
									alignItems: "center",
									justifyContent: "center",
									marginBottom: "20px",
								}}
							>
								{visiblePages.has(pageNum) ? (
									<Page
										pageNumber={pageNum}
										scale={scale}
										renderTextLayer={true}
										renderAnnotationLayer={false}
										onRenderSuccess={() => dlog(`✅ Page ${pageNum} rendered`)}
										onRenderError={(_error) => {}}
									/>
								) : (
									<div
										className="pdf-page-placeholder"
										style={{
											width: "100%",
											height: `${800 * scale}px`,
											backgroundColor: "#f5f5f5",
											display: "flex",
											alignItems: "center",
											justifyContent: "center",
											border: "1px solid #e0e0e0",
											borderRadius: "4px",
										}}
									>
										<div style={{ color: "#666" }}>Page {pageNum}</div>
									</div>
								)}
							</div>
						))}
				</Document>
			</div>
		</div>
	)
}

export default LazyPDFViewer
