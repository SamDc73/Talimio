import { Highlighter, Sparkles } from "lucide-react"
import { useEffect, useRef, useState } from "react"

/**
 * Global text selection tooltip that appears when text is selected.
 * Works with SelectionZone components to determine which handlers to call.
 *
 * This is a singleton component - only one should exist in the app.
 */
export function GlobalTextSelectionTooltip() {
	const [isOpen, setIsOpen] = useState(false)
	const [selectedText, setSelectedText] = useState("")
	const [handlers, setHandlers] = useState(null)
	const selectionTimeoutRef = useRef(null)
	const tooltipRef = useRef(null)
	const [tooltipX, setTooltipX] = useState(0)
	const [tooltipY, setTooltipY] = useState(0)

	useEffect(() => {
		const handleSelectionChange = () => {
			// Clear any pending timeout
			if (selectionTimeoutRef.current) {
				clearTimeout(selectionTimeoutRef.current)
			}

			// Debounce the selection change
			selectionTimeoutRef.current = setTimeout(() => {
				const selection = window.getSelection()
				const text = selection.toString().trim()

				if (text && text.length > 0) {
					// Find the nearest SelectionZone
					const anchorNode = selection.anchorNode
					const element = anchorNode?.nodeType === Node.TEXT_NODE ? anchorNode.parentElement : anchorNode

					const selectionZone = element?.closest?.("[data-selection-zone]")

					if (selectionZone) {
						// Get handlers from the zone's data attributes
						// We'll inject these via the SelectionZone component
						const zoneHandlers = selectionZone.__selectionHandlers

						if (zoneHandlers) {
							setSelectedText(text)
							setHandlers(zoneHandlers)

							try {
								const range = selection.getRangeAt(0)
								const rect = range.getBoundingClientRect()

								// Calculate tooltip position
								const tooltipHeight = 50
								const tooltipWidth = 200
								const padding = 10

								const x = rect.left + rect.width / 2 - tooltipWidth / 2
								const y = rect.top - tooltipHeight - padding

								setTooltipX(x)
								setTooltipY(y)
								setIsOpen(true)
							} catch (_error) {
								setIsOpen(false)
							}
						} else {
							// No handlers in this zone
							setIsOpen(false)
						}
					} else {
						// Not in a SelectionZone
						setIsOpen(false)
					}
				} else {
					setIsOpen(false)
				}
			}, 50)
		}

		const handleMouseUp = () => {
			setTimeout(handleSelectionChange, 10)
		}

		const handleClickOutside = (e) => {
			if (tooltipRef.current && !tooltipRef.current.contains(e.target)) {
				setIsOpen(false)
			}
		}

		document.addEventListener("mouseup", handleMouseUp)
		document.addEventListener("selectionchange", handleSelectionChange)
		document.addEventListener("mousedown", handleClickOutside)

		return () => {
			document.removeEventListener("mouseup", handleMouseUp)
			document.removeEventListener("selectionchange", handleSelectionChange)
			document.removeEventListener("mousedown", handleClickOutside)
			if (selectionTimeoutRef.current) {
				clearTimeout(selectionTimeoutRef.current)
			}
		}
	}, [])

	const handleHighlightClick = () => {
		if (handlers?.onHighlight) {
			handlers.onHighlight(selectedText)
		}
		setIsOpen(false)
		window.getSelection().removeAllRanges()
	}

	const handleAskAiClick = () => {
		if (handlers?.onAskAI) {
			handlers.onAskAI(selectedText)
		}
		setIsOpen(false)
		window.getSelection().removeAllRanges()
	}

	if (!isOpen || !handlers) return null

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: tooltipX,
				top: tooltipY,
				zIndex: 9999,
			}}
			className="relative"
		>
			{/* Subtle gradient background */}
			<div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 via-pink-600/20 to-orange-600/20 rounded-full blur-2xl" />

			{/* Main container with glassmorphism effect */}
			<div className="relative flex items-center gap-0.5 p-1 bg-white/10 dark:bg-gray-900/40 backdrop-blur-xl rounded-full shadow-2xl border border-white/20 dark:border-gray-700/30">
				<button
					type="button"
					onClick={handleHighlightClick}
					className="group flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-900 dark:text-white hover:bg-white/20 dark:hover:bg-white/10 rounded-full transition-all duration-200 hover:scale-105"
					title="Highlight"
				>
					<Highlighter className="w-3.5 h-3.5 transition-transform group-hover:rotate-12" />
					<span className="hidden sm:inline-block animate-in fade-in duration-200">Highlight</span>
				</button>

				<div className="w-px h-5 bg-gradient-to-b from-transparent via-gray-400/30 to-transparent dark:via-gray-600/30" />

				<button
					type="button"
					onClick={handleAskAiClick}
					className="group flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-900 dark:text-white hover:bg-white/20 dark:hover:bg-white/10 rounded-full transition-all duration-200 hover:scale-105"
					title="Ask AI"
				>
					<Sparkles className="w-3.5 h-3.5 transition-transform group-hover:rotate-12 group-hover:scale-110" />
					<span className="hidden sm:inline-block bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent font-semibold animate-in fade-in duration-200">
						Ask AI
					</span>
				</button>
			</div>
		</div>
	)
}

// Backward compatibility exports moved to separate file
// Import them directly from './text-selection-utils' if needed
