import { useEffect } from "react"

export function useContentProgressSync(setContentItems) {
	useEffect(() => {
		if (!setContentItems) {
			return undefined
		}

		let updateTimeout = null

		const handleProgressUpdated = (event) => {
			const detail = event?.detail || {}
			const { contentId, progress, metadata } = detail

			if (!contentId) {
				return
			}

			if (updateTimeout) {
				clearTimeout(updateTimeout)
			}

			updateTimeout = setTimeout(() => {
				setContentItems((previousItems) =>
					previousItems.map((item) => {
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

						const nextMetadata = metadata ? { ...(item.metadata || {}), ...metadata } : item.metadata

						return {
							...item,
							progress: nextProgress,
							...(nextMetadata ? { metadata: nextMetadata } : {}),
						}
					})
				)
			}, 150)
		}

		window.addEventListener("progressUpdated", handleProgressUpdated)

		return () => {
			if (updateTimeout) {
				clearTimeout(updateTimeout)
			}
			window.removeEventListener("progressUpdated", handleProgressUpdated)
		}
	}, [setContentItems])
}
