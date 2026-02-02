import { useEffect, useRef } from "react"

const applyProgressUpdate = (items, contentId, progress, metadata) =>
	items.map((item) => {
		if (item.id !== contentId) {
			return item
		}

		if (metadata?.content_type && item.type && item.type !== metadata.content_type) {
			return item
		}

		let nextProgress = 0
		if (typeof progress === "number") {
			nextProgress = progress
		} else if (typeof item.progress === "number") {
			nextProgress = item.progress
		}

		const nextMetadata = metadata ? { ...item.metadata, ...metadata } : item.metadata

		return {
			...item,
			progress: nextProgress,
			...(nextMetadata ? { metadata: nextMetadata } : {}),
		}
	})

const applyProgressUpdateToItems = (setContentItems, contentId, progress, metadata) => {
	setContentItems((previousItems) => applyProgressUpdate(previousItems, contentId, progress, metadata))
}

const scheduleProgressUpdate = (setContentItems, updateTimeoutRef, contentId, progress, metadata) => {
	if (updateTimeoutRef.current) {
		clearTimeout(updateTimeoutRef.current)
	}

	updateTimeoutRef.current = setTimeout(applyProgressUpdateToItems, 150, setContentItems, contentId, progress, metadata)
}

export function useContentProgressSync(setContentItems) {
	const updateTimeoutRef = useRef(null)

	useEffect(() => {
		if (!setContentItems) {
			return
		}

		const handleProgressUpdated = (event) => {
			const detail = event?.detail || {}
			const { contentId, progress, metadata } = detail

			if (!contentId) {
				return
			}

			scheduleProgressUpdate(setContentItems, updateTimeoutRef, contentId, progress, metadata)
		}

		window.addEventListener("progressUpdated", handleProgressUpdated)

		return () => {
			if (updateTimeoutRef.current) {
				clearTimeout(updateTimeoutRef.current)
				updateTimeoutRef.current = null
			}
			window.removeEventListener("progressUpdated", handleProgressUpdated)
		}
	}, [setContentItems])
}
