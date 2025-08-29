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
 * @param {Function} onHighlight - Optional handler for highlight button
 * @param {Function} onAskAI - Optional handler for Ask AI button
 *
 * @example
 * // With both handlers
 * <SelectionZone onHighlight={handleHighlight} onAskAI={handleAskAI}>
 *   <article>Content with selectable text...</article>
 * </SelectionZone>
 *
 * // Only Ask AI (e.g., for PDFs with built-in highlighting)
 * <SelectionZone onAskAI={handleAskAI}>
 *   <PDFViewer />
 * </SelectionZone>
 */
export function SelectionZone({ children, onHighlight, onAskAI }) {
	const zoneRef = useRef(null)

	// Attach handlers to DOM element for the tooltip to find
	// This is the ONLY useEffect needed - it's truly syncing with DOM
	useEffect(() => {
		const currentZone = zoneRef.current
		if (currentZone) {
			// Store handlers on the DOM element itself
			// This allows the tooltip to find them without React context
			currentZone.__selectionHandlers = { onHighlight, onAskAI }
		}

		return () => {
			if (currentZone) {
				delete currentZone.__selectionHandlers
			}
		}
	}, [onHighlight, onAskAI])

	return (
		<div ref={zoneRef} data-selection-zone="true">
			{children}
		</div>
	)
}
