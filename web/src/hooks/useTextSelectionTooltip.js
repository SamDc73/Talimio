import { useEffect, useRef } from "react"

/**
 * Hook to register text selection handlers for a component.
 * This enables the global text selection tooltip with custom actions.
 *
 * @param {Function} onHighlight - Handler for when user clicks "Highlight"
 * @param {Function} onAskAi - Handler for when user clicks "Ask AI"
 */
export const useTextSelectionTooltip = (onHighlight, onAskAi) => {
	const containerRef = useRef(null)

	// Effect to register handlers with the SelectionZone
	useEffect(() => {
		if (containerRef.current) {
			// Store handlers on the element for the GlobalTextSelectionTooltip to find
			containerRef.current.__selectionHandlers = {
				onHighlight,
				onAskAI: onAskAi,
			}
		}

		return () => {
			// Clear handlers when component unmounts to prevent memory leaks
			if (containerRef.current) {
				containerRef.current.__selectionHandlers = null
			}
		}
	}, [onHighlight, onAskAi])

	return { containerRef }
}
