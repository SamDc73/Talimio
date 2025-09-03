import { Highlighter, Sparkles } from "lucide-react"
import { useEffect, useRef, useState } from "react"

/**
 * Tooltip that appears when text is selected for creating highlights.
 * Uses the same design as GlobalTextSelectionTooltip for consistency.
 */
export function HighlightCreationTooltip({ onHighlight, onAskAI }) {
	const [isOpen, setIsOpen] = useState(false)
	const [selectedText, setSelectedText] = useState("")
	const [tooltipX, setTooltipX] = useState(0)
	const [tooltipY, setTooltipY] = useState(0)
	const tooltipRef = useRef(null)
	const selectionTimeoutRef = useRef(null)

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
					// Check if we're selecting inside an existing highlight
					const anchorNode = selection.anchorNode
					const element = anchorNode?.nodeType === Node.TEXT_NODE ? anchorNode.parentElement : anchorNode

					// Don't show tooltip if selecting within an existing highlight
					const isInHighlight = element?.closest?.(".text-highlight")
					if (isInHighlight) {
						setIsOpen(false)
						return
					}

					// Check if we're in a book viewer or content area where highlighting is enabled
					const highlightableArea = element?.closest?.(".book-viewer-container, .lesson-viewer, .video-transcript")

					if (!highlightableArea) {
						setIsOpen(false)
						return
					}

					setSelectedText(text)

					try {
						const range = selection.getRangeAt(0)
						const rect = range.getBoundingClientRect()

						// Calculate position - center horizontally
						const x = rect.left + rect.width / 2

						// Position above the selection, but ensure it stays on screen
						let y = rect.top - 60 // Default: 60px above the selection

						// If too close to top of viewport, position below instead
						if (y < 10) {
							y = rect.bottom + 10 // Position below the selection
						}

						setTooltipX(x)
						setTooltipY(y)
						setIsOpen(true)
					} catch (_error) {
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

		// Listen for selection changes
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
		if (onHighlight) {
			onHighlight(selectedText)
		}
		setIsOpen(false)
		window.getSelection().removeAllRanges()
	}

	const handleAskAiClick = () => {
		if (onAskAI) {
			onAskAI(selectedText)
		}
		setIsOpen(false)
		window.getSelection().removeAllRanges()
	}

	if (!isOpen) return null

	return (
		<div
			ref={tooltipRef}
			style={{
				position: "fixed",
				left: `${tooltipX}px`,
				top: `${tooltipY}px`,
				transform: "translateX(-50%)", // Center horizontally on the x position
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
