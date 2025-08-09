import { useEffect, useRef, useState } from "react"
import { ReactReader } from "react-reader"
import { SelectionZone } from "@/components/ui/SelectionZone"
import useAppStore from "@/stores/useAppStore"
import "./EPUBViewer.css"

// Define handlers for text selection
const handleHighlight = (_text) => {
	// Add highlight functionality here in the future
}

const handleAskAi = (_text) => {
	// Add AI functionality here in the future
}

/**
 * Enhanced EPUB Viewer using Zustand for state management
 * Replaces localStorage-based location and settings persistence with unified store
 */
function EPUBViewerV2({ url, bookInfo, onLocationChange }) {
	const renditionRef = useRef(null)
	const tocRef = useRef(null)
	const [showToc, setShowToc] = useState(false)

	// Zustand store selectors for EPUB-specific state
	const epubState = useAppStore((state) => state.books.progress[bookInfo?.id]?.epubState || {})
	const updateBookProgress = useAppStore((state) => state.updateBookProgress)
	const preferences = useAppStore((state) => state.preferences)

	// EPUB state with defaults
	const [location, setLocation] = useState(epubState.location || null)
	const [fontSize, setFontSize] = useState(epubState.fontSize || preferences.defaultZoomLevel * 100 || 100)

	// Note: Text selection handlers are now handled by SelectionZone wrapper

	/**
	 * Extract approximate page number from EPUB CFI location
	 * This is a simplified approximation
	 */
	const extractPageFromLocation = (cfi) => {
		try {
			// This is a very basic approximation
			// In a real implementation, you'd need to use the EPUB.js API
			// to get accurate page information
			const matches = cfi.match(/\/(\d+)/g)
			if (matches && matches.length > 0) {
				const lastMatch = matches[matches.length - 1]
				const pageNum = Number.parseInt(lastMatch.replace("/", ""), 10)
				return Math.max(1, Math.floor(pageNum / 2)) // Rough approximation
			}
		} catch (_error) {}
		return 1 // Default to page 1
	}

	/**
	 * Navigation methods
	 */
	const gotoPrevious = () => {
		if (renditionRef.current) {
			renditionRef.current.prev()
		}
	}

	const gotoNext = () => {
		if (renditionRef.current) {
			renditionRef.current.next()
		}
	}

	/**
	 * Handle location changes with store persistence
	 */
	const locationChanged = (epubcifi) => {
		setLocation(epubcifi)

		// Save location to store
		if (bookInfo?.id) {
			updateBookProgress(bookInfo.id, {
				epubState: {
					...epubState,
					location: epubcifi,
					lastUpdated: Date.now(),
				},
			})

			// Call parent callback if provided
			if (onLocationChange) {
				onLocationChange({
					location: epubcifi,
					// Try to extract page info if available
					currentPage: extractPageFromLocation(epubcifi),
				})
			}
		}
	}

	/**
	 * Initialize rendition with theming and saved state
	 */
	const onRendition = (rendition) => {
		renditionRef.current = rendition

		// Apply theme based on store preferences
		const themes = rendition.themes
		const isDark =
			preferences.theme === "dark" ||
			(preferences.theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)

		themes.default({
			"::selection": {
				background: "var(--primary)",
				color: "var(--primary-foreground)",
			},
			body: {
				color: isDark ? "#e5e5e5" : "#1a1a1a",
				background: isDark ? "#1a1a1a" : "#ffffff",
				"font-family": "system-ui, -apple-system, sans-serif",
				"line-height": "1.6",
				padding: "20px",
				transition: "background-color 0.3s ease, color 0.3s ease",
			},
			p: {
				margin: "1em 0",
			},
			"h1, h2, h3, h4, h5, h6": {
				color: isDark ? "#f5f5f5" : "#1a1a1a",
				margin: "1em 0 0.5em",
			},
			a: {
				color: isDark ? "#60a5fa" : "#2563eb",
				"text-decoration": "underline",
			},
			img: {
				"max-width": "100%",
				height: "auto",
			},
		})

		// Restore saved location
		if (epubState.location) {
			setLocation(epubState.location)
		}

		// Set font size
		rendition.themes.fontSize(`${fontSize}%`)
	}

	/**
	 * Set up keyboard navigation
	 */
	useEffect(() => {
		if (renditionRef.current) {
			const handleKeyPress = (e) => {
				if (e.key === "ArrowLeft" && renditionRef.current) {
					renditionRef.current.prev()
				} else if (e.key === "ArrowRight" && renditionRef.current) {
					renditionRef.current.next()
				}
			}

			document.addEventListener("keydown", handleKeyPress)
			return () => document.removeEventListener("keydown", handleKeyPress)
		}
	}, [])

	/**
	 * Font size controls with store persistence
	 */
	const increaseFontSize = () => {
		const newSize = Math.min(fontSize + 10, 200)
		setFontSize(newSize)

		if (renditionRef.current) {
			renditionRef.current.themes.fontSize(`${newSize}%`)
		}

		// Save to store
		if (bookInfo?.id) {
			updateBookProgress(bookInfo.id, {
				epubState: {
					...epubState,
					fontSize: newSize,
				},
			})
		}
	}

	const decreaseFontSize = () => {
		const newSize = Math.max(fontSize - 10, 50)
		setFontSize(newSize)

		if (renditionRef.current) {
			renditionRef.current.themes.fontSize(`${newSize}%`)
		}

		// Save to store
		if (bookInfo?.id) {
			updateBookProgress(bookInfo.id, {
				epubState: {
					...epubState,
					fontSize: newSize,
				},
			})
		}
	}

	const resetFontSize = () => {
		const defaultSize = preferences.defaultZoomLevel * 100 || 100
		setFontSize(defaultSize)

		if (renditionRef.current) {
			renditionRef.current.themes.fontSize(`${defaultSize}%`)
		}

		// Save to store
		if (bookInfo?.id) {
			updateBookProgress(bookInfo.id, {
				epubState: {
					...epubState,
					fontSize: defaultSize,
				},
			})
		}
	}

	/**
	 * Table of Contents handling
	 */
	const getToc = () => {
		return tocRef.current || []
	}

	const handleTocSelect = (href) => {
		if (renditionRef.current) {
			renditionRef.current.display(href)
			setShowToc(false)
		}
	}

	/**
	 * Theme change effect
	 */
	useEffect(() => {
		if (renditionRef.current) {
			// Re-apply theme when theme preference changes
			const themes = renditionRef.current.themes
			const isDark =
				preferences.theme === "dark" ||
				(preferences.theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)

			themes.default({
				"::selection": {
					background: "var(--primary)",
					color: "var(--primary-foreground)",
				},
				body: {
					color: isDark ? "#e5e5e5" : "#1a1a1a",
					background: isDark ? "#1a1a1a" : "#ffffff",
					"font-family": "system-ui, -apple-system, sans-serif",
					"line-height": "1.6",
					padding: "20px",
					transition: "background-color 0.3s ease, color 0.3s ease",
				},
				p: {
					margin: "1em 0",
				},
				"h1, h2, h3, h4, h5, h6": {
					color: isDark ? "#f5f5f5" : "#1a1a1a",
					margin: "1em 0 0.5em",
				},
				a: {
					color: isDark ? "#60a5fa" : "#2563eb",
					"text-decoration": "underline",
				},
				img: {
					"max-width": "100%",
					height: "auto",
				},
			})
		}
	}, [preferences.theme])

	return (
		<SelectionZone onHighlight={handleHighlight} onAskAI={handleAskAi}>
			<div className="epub-viewer-container">
				<div className="epub-controls-bar">
					<div className="epub-controls">
						<button
							type="button"
							onClick={() => setShowToc(!showToc)}
							className="epub-button"
							aria-label={showToc ? "Hide table of contents" : "Show table of contents"}
						>
							{showToc ? "Hide" : "Show"} ToC
						</button>

						<div className="font-controls">
							<button
								type="button"
								onClick={decreaseFontSize}
								className="epub-button"
								aria-label="Decrease font size"
								disabled={fontSize <= 50}
							>
								A-
							</button>

							<button
								type="button"
								onClick={resetFontSize}
								className="font-size-display epub-button"
								title="Reset to default size"
							>
								{fontSize}%
							</button>

							<button
								type="button"
								onClick={increaseFontSize}
								className="epub-button"
								aria-label="Increase font size"
								disabled={fontSize >= 200}
							>
								A+
							</button>
						</div>

						<div className="navigation-controls">
							<button type="button" onClick={gotoPrevious} className="epub-button" aria-label="Previous page">
								←
							</button>

							<button type="button" onClick={gotoNext} className="epub-button" aria-label="Next page">
								→
							</button>
						</div>
					</div>
				</div>

				{showToc && (
					<div className="epub-toc">
						<div className="epub-toc-header">
							<h3>Table of Contents</h3>
							<button
								type="button"
								onClick={() => setShowToc(false)}
								className="epub-button epub-toc-close"
								aria-label="Close table of contents"
							>
								×
							</button>
						</div>
						<ul className="epub-toc-list">
							{getToc().map((item, index) => (
								<li key={item.href || index}>
									<button
										type="button"
										onClick={() => handleTocSelect(item.href)}
										className="toc-item"
										title={item.label}
									>
										{item.label}
									</button>
								</li>
							))}
						</ul>
					</div>
				)}

				<div className="epub-reader-wrapper">
					<ReactReader
						url={url}
						location={location}
						locationChanged={locationChanged}
						getRendition={onRendition}
						tocChanged={(toc) => {
							tocRef.current = toc
						}}
						epubOptions={{
							flow: "paginated",
							manager: "continuous",
						}}
					/>
				</div>

				{/* Progress indicator */}
				{location && (
					<div className="epub-progress-indicator">
						<div className="epub-location-info">Location: {location.slice(0, 20)}...</div>
					</div>
				)}
			</div>
		</SelectionZone>
	)
}

export default EPUBViewerV2
