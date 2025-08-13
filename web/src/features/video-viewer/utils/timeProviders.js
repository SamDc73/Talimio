// timeProviders.js

class TimeProvider {
	getTime() {
		throw new Error("Must implement getTime()")
	}
	getPlaybackRate() {
		return 1
	}
	destroy() {}
}

export class HTML5TimeProvider extends TimeProvider {
	constructor(videoElement) {
		super()
		this.video = videoElement
	}

	getTime() {
		return this.video.currentTime
	}

	getPlaybackRate() {
		return this.video.playbackRate
	}
}

export class YouTubeTimeProvider extends TimeProvider {
	constructor(youtubePlayerRef) {
		super()
		this.playerRef = youtubePlayerRef // ref to YouTubePlayer
		this.currentSegmentDuration = 2
		this.cachedData = {
			time: 0,
			rate: 1,
			state: -1,
			lastSampleTime: performance.now(),
		}
		this.isPlaying = false
		this.lastStateChangeTs = performance.now()
		// Store last real sample for prediction
		this.lastRealTime = 0
		this.lastRealTimestamp = performance.now()

		// Smoothing window for measured rate/time
		this.sampleWindow = 12
		this.samples = new Float32Array(this.sampleWindow)
		this.sampleTs = new Float64Array(this.sampleWindow)
		this.sampleIdx = 0
		this.sampleCount = 0
	}

	setPlaying(isPlaying) {
		if (this.isPlaying === isPlaying) {
			// No state change; avoid spamming logs/samples
			return
		}
		this.isPlaying = isPlaying
		this.lastStateChangeTs = performance.now()
		// Sample immediately on state change
		if (this.isPlayerReady()) {
			const sampledTime = this.sampleNow()
			// If we're starting to play and haven't sampled yet, force sample
			if (isPlaying && this.lastRealTime === 0) {
				this.lastRealTime = sampledTime
				this.lastRealTimestamp = performance.now()
			}
		}
	}

	// Check if player is ready
	isPlayerReady() {
		const player = this.playerRef?.current
		return player && typeof player.isReady === "function" && player.isReady()
	}

	// Sample current time immediately (for seeking, initial load, etc.)
	sampleNow() {
		if (!this.isPlayerReady()) {
			return this.cachedData.time
		}

		try {
			const player = this.playerRef.current
			const now = performance.now()
			const currentTime = player.getCurrentTime() || 0

			this.cachedData = {
				time: currentTime,
				rate: player.getPlaybackRate() || 1,
				state: player.getPlayerState() || -1,
				lastSampleTime: now,
			}

			// Update prediction baseline + smoothing buffer
			this.lastRealTime = currentTime
			this.lastRealTimestamp = now
			this.samples[this.sampleIdx] = currentTime
			this.sampleTs[this.sampleIdx] = now
			this.sampleIdx = (this.sampleIdx + 1) % this.sampleWindow
			this.sampleCount = Math.min(this.sampleCount + 1, this.sampleWindow)

			return currentTime
		} catch (_error) {
			// Player not ready yet
			return this.cachedData.time
		}
	}

	getTime() {
		// If player isn't ready, return cached time
		if (!this.isPlayerReady()) {
			return this.cachedData.time
		}

		// Derive playing state directly from player when possible to avoid external coupling
		let derivedIsPlaying = this.isPlaying
		const player = this.playerRef.current

		try {
			const state = player.getPlayerState()
			this.cachedData.state = state
			const playerIsPlaying = state === 1 || state === 3 // PLAYING or BUFFERING
			// Favor either external signal or player state, but if paused (2) within 500ms of last change, assume playing to avoid latency.
			const withinGrace = performance.now() - this.lastStateChangeTs < 500
			derivedIsPlaying = this.isPlaying || playerIsPlaying || (withinGrace && state === 2)
			this.isPlaying = derivedIsPlaying
		} catch (_error) {
			// Player not ready yet, use cached state
		}

		// If not actively playing, return the current time directly from player for precision
		if (!derivedIsPlaying) {
			try {
				const time = player.getCurrentTime() || this.cachedData.time
				return time
			} catch (_error) {
				return this.cachedData.time
			}
		}

		// When playing, use smoothed prediction based on last samples
		const now = performance.now()
		const elapsed = (now - this.lastRealTimestamp) / 1000
		let rate = this.cachedData.rate
		// Smooth playback rate from recent samples to reduce jitter
		if (this.sampleCount >= 2) {
			const lastIdx = (this.sampleIdx - 1 + this.sampleWindow) % this.sampleWindow
			const prevIdx = (this.sampleIdx - 2 + this.sampleWindow) % this.sampleWindow
			const dt = Math.max(0.001, (this.sampleTs[lastIdx] - this.sampleTs[prevIdx]) / 1000)
			const dx = this.samples[lastIdx] - this.samples[prevIdx]
			rate = dx / dt
		}
		const predictedTime = this.lastRealTime + elapsed * rate

		// Periodically resync to prevent drift
		if (now - this.cachedData.lastSampleTime > 750) {
			this.sampleNow()
			return this.cachedData.time
		}

		return predictedTime
	}

	getPlaybackRate() {
		return this.cachedData.rate
	}

	setCurrentSegmentDuration(duration) {
		this.currentSegmentDuration = duration
	}

	getDebugInfo() {
		const now = performance.now()
		const player = this.playerRef?.current
		let playerState = this.cachedData.state
		let playerTime = this.cachedData.time
		let playerRate = this.cachedData.rate
		if (player) {
			try {
				if (typeof player.getPlayerState === "function") playerState = player.getPlayerState()
				if (typeof player.getCurrentTime === "function") playerTime = player.getCurrentTime()
				if (typeof player.getPlaybackRate === "function") playerRate = player.getPlaybackRate()
			} catch (_e) {}
		}
		const elapsed = (now - this.lastRealTimestamp) / 1000
		const predicted = this.lastRealTime + elapsed * (this.cachedData.rate || 1)
		return {
			now,
			isPlaying: this.isPlaying,
			cached: { ...this.cachedData },
			lastRealTime: this.lastRealTime,
			lastRealTimestamp: this.lastRealTimestamp,
			predictedTime: predicted,
			player: { state: playerState, time: playerTime, rate: playerRate },
		}
	}

	destroy() {
		// Clean up any references
		this.playerRef = null
		this.cachedData = {
			time: 0,
			rate: 1,
			state: -1,
			lastSampleTime: 0,
		}
	}
}
