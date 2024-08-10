import { useEffect, useRef } from "react"

/**
 * Declarative wrapper that provides text selection handlers to its children.
 * The GlobalTextSelectionTooltip will automatically use these handlers
 * when text is selected within this zone.
 *
 * This is the most future-proof solution:
 * - No useEffect in consuming components
 * - No registration/cleanup patterns
 * - Works with Suspense, ErrorBoundaries, concurrent features
 * - Pure declarative React that "just works"
 *
 * @example
 * <SelectionZone onHighlight={handleHighlight} onAskAI={handleAskAI}>
 *   <article>Content with selectable text...</article>
 * </SelectionZone>
 */
export function SelectionZone({ children, onHighlight, onAskAI }) {
	const zoneRef = useRef(null)

	// Attach handlers to DOM element for the tooltip to find
	// This is the ONLY useEffect needed - it's truly syncing with DOM
	useEffect(() => {
		if (zoneRef.current) {
			// Store handlers on the DOM element itself
			// This allows the tooltip to find them without React context
			zoneRef.current.__selectionHandlers = { onHighlight, onAskAI }
		}

		return () => {
			if (zoneRef.current) {
				delete zoneRef.current.__selectionHandlers
			}
		}
	}, [onHighlight, onAskAI])

	return (
		<div ref={zoneRef} data-selection-zone="true">
			{children}
		</div>
	)
}
