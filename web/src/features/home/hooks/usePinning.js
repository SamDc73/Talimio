import { useState } from "react"

export const usePinning = () => {
	const [pins, setPins] = useState({})

	const togglePin = (type, id) => {
		setPins((p) => ({
			...p,
			[type]: p[type]?.includes(id) ? p[type].filter((x) => x !== id) : [...(p[type] || []), id],
		}))
	}

	const initializePins = (contentItems) => {
		const initialPins = {}
		for (const item of contentItems) {
			if (!initialPins[item.type]) initialPins[item.type] = []
		}
		setPins(initialPins)
	}

	const removePinById = (itemId) => {
		setPins((prevPins) => {
			const newPins = { ...prevPins }
			for (const type of Object.keys(newPins)) {
				newPins[type] = newPins[type].filter((id) => id !== itemId)
			}
			return newPins
		})
	}

	const getPinnedItems = (filteredAndSortedContent) => {
		return Object.entries(pins).flatMap(([type, ids]) =>
			filteredAndSortedContent.filter((x) => x.type === type && ids.includes(x.id))
		)
	}

	const getUnpinnedItems = (filteredAndSortedContent) => {
		return filteredAndSortedContent.filter((i) => !pins[i.type]?.includes(i.id))
	}

	return {
		pins,
		togglePin,
		initializePins,
		removePinById,
		getPinnedItems,
		getUnpinnedItems,
	}
}
