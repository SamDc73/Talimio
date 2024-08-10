import { useEffect } from "react"

import { useTextSelection } from "@/components/ui/GlobalTextSelectionTooltip"

/**
 * Hook to register text selection handlers for a component.
 * This enables the global text selection tooltip with custom actions.
 *
 * @param {Function} onHighlight - Handler for when user clicks "Highlight"
 * @param {Function} onAskAi - Handler for when user clicks "Ask AI"
 */
export const useTextSelectionTooltip = (onHighlight, onAskAi) => {
	const { setSelectionHandlers } = useTextSelection()

	// Effect to sync handlers with the global tooltip
	// Per React docs: Effects are for external system sync
	useEffect(() => {
		setSelectionHandlers(onHighlight, onAskAi)

		return () => {
			// Clear handlers when component unmounts to prevent memory leaks
			setSelectionHandlers(null, null)
		}
	}, [onHighlight, onAskAi, setSelectionHandlers])
}
