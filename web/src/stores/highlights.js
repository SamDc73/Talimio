/**
 * Domain-bounded store for highlight-specific CLIENT state only.
 * Server data is managed by React Query.
 */

import { create } from "zustand"

const highlightStore = create((set, get) => ({
	// Client UI state only - NO server data here
	hoveredHighlightId: null,
	selectedHighlightId: null,
	isCreatingHighlight: false,

	// Actions grouped together
	actions: {
		setHoveredHighlight: (id) => set({ hoveredHighlightId: id }),
		setSelectedHighlight: (id) => set({ selectedHighlightId: id }),
		setCreatingHighlight: (isCreating) => set({ isCreatingHighlight: isCreating }),

		// Business logic in store, not components
		onHighlightClick: (highlightId) => {
			const currentSelected = get().selectedHighlightId
			if (currentSelected === highlightId) {
				set({ selectedHighlightId: null })
			} else {
				set({ selectedHighlightId: highlightId })
				// Emit event for other components
				window.dispatchEvent(new CustomEvent("highlightSelected", { detail: highlightId }))
			}
		},

		onHighlightHover: (highlightId) => {
			set({ hoveredHighlightId: highlightId })
			// Emit event for tooltip or other UI updates
			window.dispatchEvent(new CustomEvent("highlightHovered", { detail: highlightId }))
		},

		clearSelection: () => {
			set({ selectedHighlightId: null, hoveredHighlightId: null })
		},
	},
}))

// Only export custom hooks - NEVER the store
export const useHoveredHighlight = () => highlightStore((state) => state.hoveredHighlightId)
export const useSelectedHighlight = () => highlightStore((state) => state.selectedHighlightId)
export const useIsCreatingHighlight = () => highlightStore((state) => state.isCreatingHighlight)
export const useHighlightActions = () => highlightStore((state) => state.actions)
