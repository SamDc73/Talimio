import { useEffect, useRef, useState } from "react"

/**
 * Hook for web highlighter functionality
 * Provides highlighting capabilities for text selection
 */
export function useWebHighlighter(_options = {}) {
	const [highlights, setHighlights] = useState([])
	const [selectedText, setSelectedText] = useState("")
	const [selectionRange, setSelectionRange] = useState(null)
	const containerRef = useRef(null)

	// Handle text selection
	const handleTextSelection = () => {
		const selection = window.getSelection()
		if (selection?.toString().trim()) {
			setSelectedText(selection.toString())
			setSelectionRange(selection.getRangeAt(0))
		} else {
			setSelectedText("")
			setSelectionRange(null)
		}
	}

	// Add highlight
	const addHighlight = (text, range) => {
		const newHighlight = {
			id: Date.now().toString(),
			text,
			range,
			timestamp: new Date().toISOString(),
		}
		setHighlights((prev) => [...prev, newHighlight])
		clearSelection()
	}

	// Remove highlight
	const removeHighlight = (id) => {
		setHighlights((prev) => prev.filter((h) => h.id !== id))
	}

	// Clear selection
	const clearSelection = () => {
		window.getSelection()?.removeAllRanges()
		setSelectedText("")
		setSelectionRange(null)
	}

	// Set up event listeners
	useEffect(() => {
		const container = containerRef.current || document
		container.addEventListener("mouseup", handleTextSelection)
		container.addEventListener("touchend", handleTextSelection)

		return () => {
			container.removeEventListener("mouseup", handleTextSelection)
			container.removeEventListener("touchend", handleTextSelection)
		}
	}, [handleTextSelection])

	return {
		containerRef,
		highlights,
		selectedText,
		selectionRange,
		addHighlight,
		removeHighlight,
		clearSelection,
		setHighlights,
	}
}
