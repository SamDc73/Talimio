import { useEffect, useRef } from "react"

/**
 * Custom hook to manage YouTube player initialization and tracking
 * Extracted from VideoViewer to reduce complexity
 */
export function useYouTubePlayer({ video, initialTime = 0, onTimeUpdate, onDurationUpdate }) {
	const playerRef = useRef(null)
	const ytPlayerRef = useRef(null)
	const liteYoutubeEventListenerRef = useRef(null)

	useEffect(() => {
		if (!video || !playerRef.current) return

		let _ytPlayer = null
		let intervalId = null

		const initializeYouTubePlayer = () => {
			// Wait for lite-youtube to load the iframe
			const checkIframe = setInterval(() => {
				const iframe = playerRef.current?.shadowRoot?.querySelector("iframe")
				if (iframe && window.YT && window.YT.Player) {
					clearInterval(checkIframe)

					// Create YouTube player instance
					_ytPlayer = new window.YT.Player(iframe, {
						events: {
							onReady: (event) => {
								ytPlayerRef.current = event.target

								// Seek to saved position
								if (initialTime > 0) {
									event.target.seekTo(initialTime, true)
								}

								// Start progress tracking
								intervalId = setInterval(() => {
									if (ytPlayerRef.current && typeof ytPlayerRef.current.getCurrentTime === "function") {
										try {
											const time = ytPlayerRef.current.getCurrentTime()
											const totalDuration = ytPlayerRef.current.getDuration()

											if (typeof time === "number" && !Number.isNaN(time)) {
												onTimeUpdate(time)
												if (totalDuration > 0) {
													onDurationUpdate(totalDuration)
												}
											}
										} catch (_err) {
											// Silently handle errors
										}
									}
								}, 1000)
							},
						},
					})
				}
			}, 100)
		}

		const handleIframeLoaded = () => {
			setTimeout(initializeYouTubePlayer, 500)
		}

		// Load YouTube IFrame API if not already loaded
		if (!window.YT) {
			const tag = document.createElement("script")
			tag.src = "https://www.youtube.com/iframe_api"
			const firstScriptTag = document.getElementsByTagName("script")[0]
			firstScriptTag.parentNode.insertBefore(tag, firstScriptTag)

			window.onYouTubeIframeAPIReady = initializeYouTubePlayer
		} else {
			// If API is already loaded, check if iframe exists
			const iframe = playerRef.current?.shadowRoot?.querySelector("iframe")
			if (iframe) {
				initializeYouTubePlayer()
			} else {
				// Listen for iframe loaded event
				liteYoutubeEventListenerRef.current = handleIframeLoaded
				playerRef.current.addEventListener("liteYoutubeIframeLoaded", handleIframeLoaded)
			}
		}

		// Cleanup
		return () => {
			if (intervalId) {
				clearInterval(intervalId)
			}
			if (playerRef.current && liteYoutubeEventListenerRef.current) {
				playerRef.current.removeEventListener("liteYoutubeIframeLoaded", liteYoutubeEventListenerRef.current)
			}
			ytPlayerRef.current = null
		}
	}, [video, initialTime, onDurationUpdate, onTimeUpdate]) // Only depend on video, not on changing values

	const seekTo = (timestamp) => {
		if (ytPlayerRef.current && typeof ytPlayerRef.current.seekTo === "function") {
			ytPlayerRef.current.seekTo(timestamp, true)
			onTimeUpdate(timestamp)
		} else {
			// If player not ready, try iframe postMessage
			const iframe = playerRef.current?.shadowRoot?.querySelector("iframe")
			if (iframe?.contentWindow) {
				iframe.contentWindow.postMessage(
					JSON.stringify({
						event: "command",
						func: "seekTo",
						args: [timestamp, true],
					}),
					"https://www.youtube.com"
				)
				onTimeUpdate(timestamp)
			}
			return false // Indicate seek may not have worked
		}
		return true
	}

	return {
		playerRef,
		seekTo,
	}
}
