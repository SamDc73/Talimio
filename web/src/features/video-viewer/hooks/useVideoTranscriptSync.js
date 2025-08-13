// useVideoTranscriptSync.js
// 1. React imports
import { useEffect, useRef } from "react"
import { HTML5TimeProvider, YouTubeTimeProvider } from "@/features/video-viewer/utils/timeProviders"
// 3. Internal absolute imports (using @ alias pattern)
import { VideoTranscriptSync } from "@/features/video-viewer/utils/videoTranscriptSync"

export function useVideoTranscriptSync({
	videoElement,
	youtubePlayerRef,
	segments,
	onActiveIndexChange,
	scrollToIndex,
	onTimeUpdate,
	isPlaying = true, // New prop to control play/pause
}) {
	const syncRef = useRef(null)

	useEffect(() => {
		if (!segments?.length) return

		let timeProvider = null

		if (videoElement) {
			timeProvider = new HTML5TimeProvider(videoElement)
		} else if (youtubePlayerRef?.current?.isReady?.()) {
			// Only create TimeProvider when player is actually ready
			timeProvider = new YouTubeTimeProvider(youtubePlayerRef)
			// Sample initial time immediately for YouTube
			if (timeProvider.sampleNow) {
				timeProvider.sampleNow()
			}
			// Set initial playing state
			if (timeProvider.setPlaying) {
				timeProvider.setPlaying(isPlaying)
			}
		} else {
			return
		}

		// Use the optimized sync engine (handles Firefox and YouTube optimizations internally)
		syncRef.current = new VideoTranscriptSync(timeProvider, segments, onActiveIndexChange, scrollToIndex, onTimeUpdate)

		// Always keep the sync engine running; it self-adjusts using provider state
		syncRef.current.play()

		return () => {
			syncRef.current?.destroy()
			syncRef.current = null
		}
	}, [videoElement, youtubePlayerRef, segments, onActiveIndexChange, scrollToIndex, onTimeUpdate, isPlaying]) // isPlaying is used only to trigger tick updates

	// Reflect play/pause changes to both the sync engine and the time provider
	useEffect(() => {
		if (syncRef.current) {
			if (isPlaying) {
				syncRef.current.play()
			} else {
				syncRef.current.pause()
			}
		}
		if (syncRef.current?.timeProvider?.setPlaying) {
			syncRef.current.timeProvider.setPlaying(isPlaying)
		}
	}, [isPlaying])

	return syncRef.current
}
