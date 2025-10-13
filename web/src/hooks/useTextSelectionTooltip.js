import { useEffect, useRef } from "react"

/**
 * Hook to register Ask AI handler for a component so the tooltip can surface it.
 */
export const useTextSelectionTooltip = (onAskAi) => {
	const containerRef = useRef(null)

	useEffect(() => {
		const element = containerRef.current
		if (element) {
			element.__selectionHandlers = {
				onAskAI: onAskAi,
			}
			element.setAttribute("data-selection-zone", "true")
		}

		return () => {
			if (element) {
				delete element.__selectionHandlers
				element.removeAttribute("data-selection-zone")
			}
		}
	}, [onAskAi])

	return { containerRef }
}
