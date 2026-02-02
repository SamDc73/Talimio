// YouTubePlayer.jsx
import { memo, useEffect, useImperativeHandle, useRef } from "react"

// Load YouTube IFrame API script
const loadYouTubeAPI = () => {
	return new Promise((resolve, reject) => {
		if (window.YT?.Player) {
			resolve()
			return
		}

		const tag = document.createElement("script")
		tag.src = "https://www.youtube.com/iframe_api"
		tag.addEventListener("error", () => reject(new Error("Failed to load YouTube API")))

		const firstScriptTag = document.getElementsByTagName("script")[0]
		if (firstScriptTag?.parentNode) {
			firstScriptTag.parentNode.insertBefore(tag, firstScriptTag)
		} else {
			document.head.append(tag)
		}

		// Store previous callback to avoid conflicts
		const previousCallback = window.onYouTubeIframeAPIReady
		window.onYouTubeIframeAPIReady = () => {
			// Call previous callback if it exists
			if (previousCallback && typeof previousCallback === "function") {
				previousCallback()
			}
			// Cleanup to prevent memory leaks
			window.onYouTubeIframeAPIReady = undefined
			resolve()
		}

		// Timeout after 10 seconds
		setTimeout(() => {
			window.onYouTubeIframeAPIReady = undefined
			reject(new Error("YouTube API load timeout"))
		}, 10_000)
	})
}

// Memoize the component to prevent recreation when parent re-renders
function YouTubePlayerBase({
	videoId,
	onReady,
	onStateChange,
	onPlaybackRateChange,
	onError,
	width = "100%",
	height = "100%",
	playerVars = {},
	ref, // ref is a regular prop in React 19
}) {
	const containerRef = useRef(null)
	const playerRef = useRef(null)
	const pollingIntervalRef = useRef(null)
	const lastPolledTime = useRef(0)
	const lastPolledWall = useRef(performance.now())
	const playbackRateRef = useRef(1)
	const isPlayingRef = useRef(false)

	// Store callbacks in refs to avoid dependency issues
	const onReadyRef = useRef(onReady)
	const onStateChangeRef = useRef(onStateChange)
	const onPlaybackRateChangeRef = useRef(onPlaybackRateChange)
	const onErrorRef = useRef(onError)

	// Update refs when props change
	useEffect(() => {
		onReadyRef.current = onReady
		onStateChangeRef.current = onStateChange
		onPlaybackRateChangeRef.current = onPlaybackRateChange
		onErrorRef.current = onError
	})

	// Expose player API methods via useImperativeHandle
	useImperativeHandle(ref, () => ({
		// Check if player is ready
		isReady: () => !!playerRef.current && typeof playerRef.current.getPlayerState === "function",

		// Direct API access methods
		getCurrentTime: () => playerRef.current?.getCurrentTime() || 0,
		getDuration: () => playerRef.current?.getDuration() || 0,
		getPlaybackRate: () => playerRef.current?.getPlaybackRate() || 1,
		getPlayerState: () => playerRef.current?.getPlayerState() || -1,
		getVideoUrl: () => playerRef.current?.getVideoUrl() || "",

		// Playback control
		playVideo: () => playerRef.current?.playVideo(),
		pauseVideo: () => playerRef.current?.pauseVideo(),
		stopVideo: () => playerRef.current?.stopVideo(),
		seekTo: (seconds, allowSeekAhead = true) => playerRef.current?.seekTo(seconds, allowSeekAhead),

		// Volume control
		mute: () => playerRef.current?.mute(),
		unMute: () => playerRef.current?.unMute(),
		isMuted: () => playerRef.current?.isMuted() || false,
		setVolume: (volume) => playerRef.current?.setVolume(volume),
		getVolume: () => playerRef.current?.getVolume() || 0,

		// Playback rate
		setPlaybackRate: (rate) => playerRef.current?.setPlaybackRate(rate),
		getAvailablePlaybackRates: () => playerRef.current?.getAvailablePlaybackRates() || [1],

		// Custom polling control
		startPolling: (callback, interval = 180, forcePolling = false) => {
			// Stop any existing polling
			if (pollingIntervalRef.current) {
				clearInterval(pollingIntervalRef.current)
				pollingIntervalRef.current = null
			}
			pollingIntervalRef.current = setInterval(() => {
				// Allow polling even when paused if forcePolling is true (for UI updates)
				if (playerRef.current && (forcePolling || isPlayingRef.current)) {
					const currentTime = playerRef.current.getCurrentTime()
					const now = performance.now()

					// Update cached values for prediction
					lastPolledTime.current = currentTime
					lastPolledWall.current = now
					playbackRateRef.current = playerRef.current.getPlaybackRate()

					callback({
						currentTime,
						playbackRate: playbackRateRef.current,
						playerState: playerRef.current.getPlayerState(),
						duration: playerRef.current.getDuration(),
					})
				}
			}, interval)
		},

		stopPolling: () => {
			if (pollingIntervalRef.current) {
				clearInterval(pollingIntervalRef.current)
				pollingIntervalRef.current = null
			}
		},

		// Get predicted time between polls
		getPredictedTime: () => {
			const elapsed = (performance.now() - lastPolledWall.current) / 1000
			return lastPolledTime.current + elapsed * playbackRateRef.current
		},

		// Direct player instance access (escape hatch)
		getPlayerInstance: () => playerRef.current,
	}))

	useEffect(() => {
		let mounted = true

		// Define stopPolling locally to avoid dependency issues
		const stopPolling = () => {
			if (pollingIntervalRef.current) {
				clearInterval(pollingIntervalRef.current)
				pollingIntervalRef.current = null
			}
		}

		const initPlayer = async () => {
			try {
				await loadYouTubeAPI()
			} catch (error) {
				if (onErrorRef.current) onErrorRef.current({ error })
				return
			}

			if (!mounted || !containerRef.current) return

			playerRef.current = new window.YT.Player(containerRef.current, {
				width,
				height,
				videoId,
				playerVars: {
					autoplay: 0,
					controls: 1,
					modestbranding: 1,
					rel: 0,
					showinfo: 0,
					origin: window.location.origin,
					enablejsapi: 1, // Always enable for polling
					playsinline: 1, // Better mobile experience
					...playerVars,
				},
				events: {
					onReady: (event) => {
						if (onReadyRef.current) onReadyRef.current(event)
					},
					onStateChange: (event) => {
						isPlayingRef.current = event.data === window.YT.PlayerState.PLAYING

						// Auto-stop polling when not playing
						if (!isPlayingRef.current && pollingIntervalRef.current) {
							stopPolling()
						}

						if (onStateChangeRef.current) onStateChangeRef.current(event)
					},
					onPlaybackRateChange: (event) => {
						playbackRateRef.current = event.data
						if (onPlaybackRateChangeRef.current) onPlaybackRateChangeRef.current(event)
					},
					onError: (event) => {
						if (onErrorRef.current) onErrorRef.current(event)
					},
				},
			})
		}

		initPlayer()

		return () => {
			mounted = false
			stopPolling()
			if (playerRef.current?.destroy) {
				playerRef.current.destroy()
			}
		}
		// Re-initialize when key dependencies change
		// Callbacks are handled via refs to avoid unnecessary recreations
	}, [videoId, width, height, playerVars])

	return <div ref={containerRef} className="absolute inset-0 size-full " />
}

// Export memoized component to prevent unnecessary re-renders
// It will only re-render if props actually change (shallow comparison)
export const YouTubePlayer = memo(YouTubePlayerBase)
