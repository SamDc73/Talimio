// No imports needed for this hook

export const useCelebration = () => {
	const priority = (i) => {
		if (i.progress === 100 || (i.type === "flashcards" && i.due === 0 && i.overdue === 0)) return 5
		if (i.isPaused) return 3
		if (!i.dueDate) return 4
		const h = (new Date(i.dueDate) - Date.now()) / 36e5
		return h < 0 ? 1 : h < 24 ? 2 : 4
	}

	const shouldShowCelebration = (unpinnedItems) => {
		return unpinnedItems.length > 0 && unpinnedItems.every((i) => priority(i) === 5)
	}

	return {
		priority,
		shouldShowCelebration,
	}
}
