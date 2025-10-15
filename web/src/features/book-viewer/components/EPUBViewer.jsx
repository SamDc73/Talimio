import { useCallback, useEffect, useRef, useState } from "react"
import { ReactReader } from "react-reader"
import { useBookActions, useBookReadingState, useBookZoomLevel } from "../../hooks/useBookState"

function EPUBViewer({ url, bookId, onProgressUpdate }) {
	const [location, setLocation] = useState(null)
	const [firstRenderDone, setFirstRenderDone] = useState(false)
	const renditionRef = useRef(null)
	const [epubUrl, setEpubUrl] = useState(null)
	const objectUrlRef = useRef(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)

	// Zustand reading state for initial EPUB location
	const readingState = useBookReadingState(bookId)

	// Get font size from store (use zoomLevel as fontSize for EPUBs)
	const fontSize = useBookZoomLevel(bookId)

	// Get book actions
	const { onEpubLocationChange } = useBookActions()

	// Handle location changes - memoized with proper dependencies
	const locationChanged = useCallback(
		(epubcifi) => {
			setLocation(epubcifi)

			// Persist location and progress via store
			if (firstRenderDone && epubcifi) {
				// Get progress percentage from rendition if available
				let displayPercentage
				if (renditionRef.current) {
					const { displayed } = renditionRef.current.location.start
					displayPercentage = displayed?.percentage
				}

				// Update location and progress in store (all business logic handled in action)
				onEpubLocationChange(bookId, epubcifi, displayPercentage)

				// Report progress if callback provided (for parent component)
				// The store now handles progress calculation, we just pass through the calculated value
				if (onProgressUpdate && displayPercentage !== undefined) {
					onProgressUpdate(Math.round(displayPercentage * 100))
				}
			}
		},
		[firstRenderDone, bookId, onProgressUpdate, onEpubLocationChange]
	)

	// Apply font size changes
	const applyFontSize = useCallback(() => {
		if (renditionRef.current) {
			// Convert percentage to actual font size
			const baseFontSize = 18 // Base font size in px
			const actualFontSize = (baseFontSize * fontSize) / 100

			renditionRef.current.themes.register("custom", {
				body: {
					"font-family": "'Roboto', -apple-system, BlinkMacSystemFont, sans-serif !important",
					"font-size": `${actualFontSize}px !important`,
					"line-height": "1.8 !important",
					padding: "40px 60px !important",
					"max-width": "100% !important",
					margin: "0 auto !important",
				},
				p: {
					"margin-bottom": "1.5em !important",
					"font-size": `${actualFontSize}px !important`,
				},
				h1: {
					"font-size": `${actualFontSize * 1.8}px !important`,
					margin: "2em 0 1em 0 !important",
				},
				h2: {
					"font-size": `${actualFontSize * 1.5}px !important`,
					margin: "1.5em 0 0.75em 0 !important",
				},
				h3: {
					"font-size": `${actualFontSize * 1.25}px !important`,
					margin: "1.25em 0 0.5em 0 !important",
				},
			})
			renditionRef.current.themes.select("custom")
		}
	}, [fontSize])

	// Get TOC when book loads - memoized
	const getRendition = useCallback(
		(rendition) => {
			renditionRef.current = rendition

			// Apply initial font size
			applyFontSize()

			// Disable keyboard navigation
			if (rendition) {
				// Override navigation methods
				rendition.prev = () => {} // Disable prev navigation
				rendition.next = () => {} // Disable next navigation

				// Remove keyboard event listeners
				if (rendition.manager?.container) {
					const container = rendition.manager.container
					// Remove any existing keyboard listeners
					container.removeEventListener("keydown", rendition.handleKeyPress)
					container.removeEventListener("keyup", rendition.handleKeyPress)
				}
			}

			// Navigation is now hidden via the styles prop in ReactReader

			// Get saved location from store (Zustand)
			const savedLocation = readingState?.epubState?.location
			if (savedLocation) {
				setLocation(savedLocation)
			}

			setFirstRenderDone(true)
		},
		[applyFontSize, readingState]
	)

	// Update font size when it changes
	useEffect(() => {
		if (renditionRef.current && firstRenderDone) {
			applyFontSize()
		}
	}, [applyFontSize, firstRenderDone])

	// Hide navigation elements via CSS injection (cleanest workaround for react-reader's hardcoded arrows)
	useEffect(() => {
		const style = document.createElement("style")
		style.textContent = `
      /* Hide react-reader navigation arrows - optimized selectors */
      .epub-container button[style*="font-size: 64px"],
      .epub-container button[style*="margin-top: -32px"] {
        display: none !important;
      }
    `
		document.head.appendChild(style)

		return () => {
			if (style.parentNode) {
				style.parentNode.removeChild(style)
			}
		}
	}, [])

	// Handle window resize
	useEffect(() => {
		const handleResize = () => {
			if (renditionRef.current) {
				renditionRef.current.resize()
			}
		}

		window.addEventListener("resize", handleResize)
		return () => window.removeEventListener("resize", handleResize)
	}, [])

	// Load EPUB file as blob URL
	useEffect(() => {
		const loadEpub = async () => {
			try {
				setLoading(true)
				setError(null)

				// Fetch the EPUB file with credentials
				const response = await fetch(url, {
					credentials: "include",
					headers: {
						accept: "application/epub+zip, application/octet-stream",
					},
				})

				if (!response.ok) {
					throw new Error(`Failed to load EPUB: ${response.statusText}`)
				}

				// Verify content type and binary signature (must be a ZIP for EPUB)
				const contentType = response.headers.get("content-type") || ""
				const blob = await response.blob()
				const head = await blob.slice(0, 4).arrayBuffer()
				const b = new Uint8Array(head)
				const looksLikeZip =
					b.length >= 4 && b[0] === 0x50 && b[1] === 0x4b && (b[2] === 0x03 || b[2] === 0x05 || b[2] === 0x07)

				if (!looksLikeZip) {
					throw new Error(
						`Invalid EPUB response (not a ZIP). content-type=${contentType || "unknown"}. Ensure the URL points to the binary .epub download endpoint.`
					)
				}

				// Normalize MIME to application/epub+zip for downstream consumers
				const epubBlob =
					blob.type === "application/epub+zip" ? blob : new Blob([blob], { type: "application/epub+zip" })

				// Revoke previous URL if it exists
				if (objectUrlRef.current) {
					URL.revokeObjectURL(objectUrlRef.current)
				}

				// Provide a Blob URL to ReactReader/epub.js for broad compatibility
				const objectUrl = URL.createObjectURL(epubBlob)
				objectUrlRef.current = objectUrl
				setEpubUrl(objectUrl)
				setLoading(false)
			} catch (err) {
				setError(err.message)
				setLoading(false)
			}
		}

		if (url) {
			loadEpub()
		}

		// Cleanup blob URL on unmount or url change
		return () => {
			if (objectUrlRef.current) {
				URL.revokeObjectURL(objectUrlRef.current)
				objectUrlRef.current = null
			}
		}
	}, [url])

	// Show loading state
	if (loading) {
		return (
			<div className="h-full flex items-center justify-center bg-background">
				<div className="text-center">
					<div className="mb-4">
						<div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
					</div>
					<p className="text-muted-foreground">Loading EPUB...</p>
				</div>
			</div>
		)
	}

	// Show error state
	if (error) {
		return (
			<div className="h-full flex items-center justify-center bg-background">
				<div className="text-center max-w-md">
					<h3 className="text-lg font-semibold text-destructive mb-2">Failed to load EPUB</h3>
					<p className="text-muted-foreground">{error}</p>
				</div>
			</div>
		)
	}

	// Show reader when EPUB is loaded
	if (!epubUrl) {
		return null
	}

	return (
		<div className="h-full bg-background epub-container">
			<div className="max-w-4xl mx-auto p-8 h-full">
				<div className="bg-card rounded-lg shadow-sm h-full">
					<ReactReader
						url={epubUrl}
						location={location}
						locationChanged={locationChanged}
						getRendition={getRendition}
						showToc={false}
						swipeable={false}
						epubOptions={{
							flow: "scrolled",
							manager: "continuous",
							spread: "none",
							restore: false,
							width: "100%",
							height: "100%",
							allowScriptedContent: false,
						}}
						epubInitOptions={{
							openAs: "epub",
							replacements: "blobUrl",
						}}
						styles={{
							container: {
								height: "100%",
								width: "100%",
								backgroundColor: "transparent",
							},
							readerArea: {
								position: "relative",
								height: "100%",
								width: "100%",
								display: "flex",
								flexDirection: "column",
								backgroundColor: "transparent",
								transition: "all 0.3s ease",
							},
							reader: {
								flex: 1,
								backgroundColor: "transparent",
								maxWidth: "100%",
								margin: "0 auto",
								padding: "2rem",
							},
							// Hide navigation arrows completely
							arrow: {
								display: "none",
								visibility: "hidden",
								opacity: 0,
								pointerEvents: "none",
								width: 0,
								height: 0,
							},
							arrowHover: {
								display: "none",
								visibility: "hidden",
								opacity: 0,
								pointerEvents: "none",
								width: 0,
								height: 0,
							},
							// Hide TOC UI completely
							tocBackground: {
								display: "none",
								visibility: "hidden",
							},
							tocArea: {
								display: "none",
								visibility: "hidden",
							},
							tocButton: {
								display: "none",
								visibility: "hidden",
								opacity: 0,
								pointerEvents: "none",
								width: 0,
								height: 0,
							},
							tocButtonExpanded: {
								display: "none",
								visibility: "hidden",
							},
						}}
					/>
				</div>
			</div>
		</div>
	)
}

export default EPUBViewer
