import { useEffect, useRef } from "react"
import { getApiUrl } from "@/lib/apiBase"
import { CSRF_HEADER_NAME, getCsrfToken } from "@/lib/csrf"

/**
 * Hook to handle video progress saving
 * Saves progress periodically and on unmount
 */
export function useVideoProgressSaving({ video, videoId, currentTime, duration, updateProgress }) {
	const progressDataRef = useRef({ currentTime: 0, duration: 0 })
	const lastSavedTimeRef = useRef(0)

	// Update ref whenever values change
	useEffect(() => {
		progressDataRef.current = { currentTime, duration }
	}, [currentTime, duration])

	// Save progress periodically
	useEffect(() => {
		if (!video || !videoId) return

		const saveProgress = () => {
			const { currentTime: time, duration: dur } = progressDataRef.current
			// Only save if position changed by at least 5 seconds
			if (time > 0 && Math.abs(time - lastSavedTimeRef.current) >= 5) {
				updateProgress(Math.floor(time), dur)
				lastSavedTimeRef.current = time
			}
		}

		// Save every 10 seconds (reduced frequency)
		const saveInterval = setInterval(saveProgress, 10_000)

		return () => {
			clearInterval(saveInterval)
			// Save on unmount
			saveProgress()
		}
	}, [videoId, video, updateProgress])

	// Save progress on page unload
	useEffect(() => {
		const handleBeforeUnload = () => {
			if (currentTime > 0 && video && videoId) {
				const csrfToken = getCsrfToken()
				const data = JSON.stringify({
					progress_percentage: duration > 0 ? Math.round((currentTime / duration) * 100) : 0,
					metadata: {
						content_type: "video",
						position: Math.floor(currentTime),
						duration,
					},
				})

				const headers = { "Content-Type": "application/json" }
				if (csrfToken) {
					headers[CSRF_HEADER_NAME] = csrfToken
				}
				void fetch(getApiUrl(`/progress/${videoId}`), {
					method: "PUT",
					headers,
					body: data,
					credentials: "include",
					keepalive: true,
				})
			}
		}

		window.addEventListener("beforeunload", handleBeforeUnload)
		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload)
		}
	}, [currentTime, duration, video, videoId])
}
