import { act, renderHook } from "@testing-library/react"

import { useContentProgressSync } from "../useContentProgressSync"

// Mock zustand store
jest.mock("@/stores/useAppStore", () => ({
	getState: jest.fn(() => ({
		course: {
			progressStats: {
				"course-123": {
					completion_percentage: 75,
				},
			},
		},
	})),
}))

describe("useContentProgressSync", () => {
	let setContentItems

	beforeEach(() => {
		setContentItems = jest.fn()
		// Clear all event listeners
		window.removeEventListener = jest.fn()
	})

	afterEach(() => {
		jest.clearAllTimers()
		jest.clearAllMocks()
	})

	test("listens for course progress updates", () => {
		jest.useFakeTimers()

		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		// Initial content items
		const contentItems = [
			{ id: "course-123", type: "course", progress: 0 },
			{ id: "book-456", type: "book", progress: 0 },
		]

		setContentItems.mockImplementation((callback) => {
			return callback(contentItems)
		})

		// Dispatch course progress update event
		act(() => {
			window.dispatchEvent(
				new CustomEvent("courseProgressUpdate", {
					detail: {
						courseId: "course-123",
						progressStats: { completion_percentage: 50 },
					},
				})
			)
		})

		// Fast-forward timers
		act(() => {
			jest.advanceTimersByTime(300)
		})

		// Verify setContentItems was called with updated progress
		expect(setContentItems).toHaveBeenCalled()
		const updateFunction = setContentItems.mock.calls[0][0]
		const updatedItems = updateFunction(contentItems)

		expect(updatedItems[0].progress).toBe(50)
		expect(updatedItems[1].progress).toBe(0) // Book progress unchanged

		unmount()
	})

	test("listens for book progress updates", () => {
		jest.useFakeTimers()

		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		const contentItems = [
			{ id: "course-123", type: "course", progress: 0 },
			{ id: "book-456", type: "book", progress: 0 },
		]

		setContentItems.mockImplementation((callback) => {
			return callback(contentItems)
		})

		// Dispatch book progress update event
		act(() => {
			window.dispatchEvent(
				new CustomEvent("bookProgressUpdate", {
					detail: {
						bookId: "book-456",
						stats: { percentage: 25 },
					},
				})
			)
		})

		// Fast-forward timers
		act(() => {
			jest.advanceTimersByTime(300)
		})

		// Verify setContentItems was called with updated progress
		expect(setContentItems).toHaveBeenCalled()
		const updateFunction = setContentItems.mock.calls[0][0]
		const updatedItems = updateFunction(contentItems)

		expect(updatedItems[0].progress).toBe(0) // Course progress unchanged
		expect(updatedItems[1].progress).toBe(0.25) // Book progress is 25% (25/100)

		unmount()
	})

	test("listens for video progress updates", () => {
		jest.useFakeTimers()

		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		const contentItems = [{ id: "video-789", type: "video", progress: 0 }]

		setContentItems.mockImplementation((callback) => {
			return callback(contentItems)
		})

		// Dispatch video progress update event with position/duration
		act(() => {
			window.dispatchEvent(
				new CustomEvent("videoProgressUpdate", {
					detail: {
						videoId: "video-789",
						progress: { position: 300, duration: 600 },
					},
				})
			)
		})

		// Fast-forward timers
		act(() => {
			jest.advanceTimersByTime(300)
		})

		// Verify setContentItems was called with updated progress
		expect(setContentItems).toHaveBeenCalled()
		const updateFunction = setContentItems.mock.calls[0][0]
		const updatedItems = updateFunction(contentItems)

		expect(updatedItems[0].progress).toBe(0.5) // 50% progress (300/600)

		unmount()
	})

	test("handles video progress with percentage", () => {
		jest.useFakeTimers()

		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		const contentItems = [{ id: "video-789", type: "video", progress: 0 }]

		setContentItems.mockImplementation((callback) => {
			return callback(contentItems)
		})

		// Dispatch video progress update event with percentage
		act(() => {
			window.dispatchEvent(
				new CustomEvent("videoProgressUpdate", {
					detail: {
						videoId: "video-789",
						progress: { percentage: 75 },
					},
				})
			)
		})

		// Fast-forward timers
		act(() => {
			jest.advanceTimersByTime(300)
		})

		// Verify setContentItems was called with updated progress
		expect(setContentItems).toHaveBeenCalled()
		const updateFunction = setContentItems.mock.calls[0][0]
		const updatedItems = updateFunction(contentItems)

		expect(updatedItems[0].progress).toBe(0.75) // 75% progress

		unmount()
	})

	test("throttles multiple rapid updates", () => {
		jest.useFakeTimers()

		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		// Dispatch multiple rapid course updates
		act(() => {
			for (let i = 1; i <= 5; i++) {
				window.dispatchEvent(
					new CustomEvent("courseProgressUpdate", {
						detail: {
							courseId: "course-123",
							progressStats: { completion_percentage: i * 10 },
						},
					})
				)
			}
		})

		// Fast-forward timers
		act(() => {
			jest.advanceTimersByTime(300)
		})

		// Should only call setContentItems once due to throttling
		expect(setContentItems).toHaveBeenCalledTimes(1)

		unmount()
	})

	test("cleans up event listeners on unmount", () => {
		const { unmount } = renderHook(() => useContentProgressSync(setContentItems))

		unmount()

		// Verify all event listeners are removed
		expect(window.removeEventListener).toHaveBeenCalledWith("courseProgressRefresh", expect.any(Function))
		expect(window.removeEventListener).toHaveBeenCalledWith("courseProgressUpdate", expect.any(Function))
		expect(window.removeEventListener).toHaveBeenCalledWith("bookProgressUpdate", expect.any(Function))
		expect(window.removeEventListener).toHaveBeenCalledWith("videoProgressUpdate", expect.any(Function))
	})
})
