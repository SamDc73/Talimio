// videoTranscriptSync.js
// SIMPLIFIED VERSION - MATCHING youtube-transcript-player APPROACH

export class VideoTranscriptSync {
	constructor(timeProvider, segments, onActiveChange, scrollCallback, onTimeUpdate) {
		if (!timeProvider) {
			throw new Error("VideoTranscriptSync: timeProvider is required")
		}
		if (!Array.isArray(segments)) {
			throw new Error("VideoTranscriptSync: segments must be an array")
		}

		this.timeProvider = timeProvider
		this.segments = segments
		this.onActiveChange = onActiveChange
		this.scrollCallback = scrollCallback
		this.onTimeUpdate = onTimeUpdate

		// Typed arrays for performance
		this.startTimes = new Float32Array(segments.length)
		this.endTimes = new Float32Array(segments.length)

		segments.forEach((seg, i) => {
			if (!seg || typeof seg.startTime !== "number" || typeof seg.endTime !== "number") {
				this.startTimes[i] = 0
				this.endTimes[i] = 0
			} else {
				this.startTimes[i] = seg.startTime
				this.endTimes[i] = seg.endTime
			}
		})

		// State tracking
		this.activeIndex = -1
		this.isDestroyed = false
		this.isPaused = true // Start paused, wait for explicit play
		this.intervalId = null

		// Fixed time offset (300ms lookahead like youtube-transcript-player)
		this.timeOffset = 0.3
		this.lastScrollTime = 0
	}

	// Find segment containing exact time (no offset) - used for seeking
	findSegmentForTime(time) {
		const len = this.startTimes.length
		if (len === 0) return -1

		// Binary search for exact segment containing the time
		let left = 0
		let right = len - 1

		while (left <= right) {
			const mid = Math.floor((left + right) / 2)

			if (time >= this.startTimes[mid] && time <= this.endTimes[mid]) {
				return mid
			}
			if (time < this.startTimes[mid]) {
				right = mid - 1
			} else {
				left = mid + 1
			}
		}

		// If no exact match, find the closest segment
		// Return the segment that should be active at this time
		for (let i = 0; i < len; i++) {
			if (time >= this.startTimes[i] && time <= this.endTimes[i]) {
				return i
			}
		}

		// If between segments, return the most recent one that ended
		let lastEndedIndex = -1
		for (let i = 0; i < len; i++) {
			if (time >= this.endTimes[i]) {
				lastEndedIndex = i
			} else {
				break
			}
		}

		return lastEndedIndex
	}

	// Simple binary search for active segment during playback (with lookahead)
	getActiveSegmentIndex(currentTime) {
		// Apply fixed offset (300ms lookahead)
		const time = currentTime + this.timeOffset
		const len = this.startTimes.length

		if (len === 0) return -1

		// Binary search for O(log n) performance
		let left = 0
		let right = len - 1
		let activeIndex = -1

		while (left <= right) {
			const mid = Math.floor((left + right) / 2)

			if (time >= this.startTimes[mid] && time <= this.endTimes[mid]) {
				return mid
			}
			if (time < this.startTimes[mid]) {
				right = mid - 1
			} else {
				left = mid + 1
				// Keep track of the last segment we've passed
				if (time > this.endTimes[mid]) {
					activeIndex = mid
				}
			}
		}

		// If we're between segments, return the most recent segment that has ended
		return activeIndex
	}

	// Update active segment and trigger callbacks
	updateActiveSegment(newIndex) {
		if (newIndex !== this.activeIndex) {
			this.activeIndex = newIndex

			// Notify parent
			if (this.onActiveChange) {
				this.onActiveChange(newIndex)
			}

			// Scroll to active segment with debouncing
			const now = performance.now() / 1000
			if (now - this.lastScrollTime > 0.3) {
				// 300ms debounce
				if (this.scrollCallback && newIndex >= 0 && newIndex < this.segments.length) {
					this.scrollCallback(newIndex)
				}
				this.lastScrollTime = now
			}
		}
	}

	// Simple 60fps polling loop
	startTimeTracking() {
		const trackTime = () => {
			if (this.isDestroyed) return

			if (!this.isPaused && this.timeProvider) {
				// Sample fresh time if available
				if (this.timeProvider.sampleNow) {
					this.timeProvider.sampleNow()
				}

				const currentTime = this.timeProvider.getTime()

				// Don't update when time is 0 (not started)
				if (currentTime > 0.1) {
					// Notify time update
					if (this.onTimeUpdate) {
						this.onTimeUpdate(currentTime)
					}

					// Check for active segment change
					const activeIndex = this.getActiveSegmentIndex(currentTime)
					this.updateActiveSegment(activeIndex)
				}
			}
		}

		// Use 60fps polling (16ms interval) like youtube-transcript-player
		this.intervalId = setInterval(trackTime, 16)
	}

	// Stop the polling loop
	stopTimeTracking() {
		if (this.intervalId) {
			clearInterval(this.intervalId)
			this.intervalId = null
		}
	}

	pause() {
		this.isPaused = true
		this.stopTimeTracking()
		// Update position once when pausing
		this.tickOnce()
	}

	play() {
		this.isPaused = false
		if (!this.intervalId) {
			this.startTimeTracking()
		}
	}

	// Single sync update (useful when paused)
	tickOnce() {
		if (this.timeProvider) {
			// Sample fresh time
			if (this.timeProvider.sampleNow) {
				this.timeProvider.sampleNow()
			}

			const currentTime = this.timeProvider.getTime()

			if (currentTime > 0.1) {
				if (this.onTimeUpdate) {
					this.onTimeUpdate(currentTime)
				}

				const activeIndex = this.getActiveSegmentIndex(currentTime)
				this.updateActiveSegment(activeIndex)
			}
		}
	}

	seek(time) {
		// Sample fresh time after seek
		if (this.timeProvider?.sampleNow) {
			this.timeProvider.sampleNow()
		}

		// Find the segment that contains the exact seek time (no offset manipulation)
		const activeIndex = this.findSegmentForTime(time)

		if (activeIndex !== this.activeIndex) {
			this.activeIndex = activeIndex

			if (this.onActiveChange) {
				this.onActiveChange(activeIndex)
			}

			// Immediate scroll on seek
			if (this.scrollCallback && activeIndex >= 0 && activeIndex < this.segments.length) {
				this.scrollCallback(activeIndex)
			}
		}
	}

	destroy() {
		this.isDestroyed = true
		this.stopTimeTracking()
		if (this.timeProvider?.destroy) {
			this.timeProvider.destroy()
		}
	}
}
