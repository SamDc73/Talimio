/**
 * Quick test to verify all three progress hooks have identical interfaces
 */

import { renderHook } from "@testing-library/react";
import { useBookProgress } from "../useBookProgress";
import { useCourseProgress } from "../useCourseProgress";
import { useVideoProgress } from "../useVideoProgress";

// Mock dependencies
jest.mock("../../stores/useAppStore");
jest.mock("../use-toast", () => ({
	useToast: () => ({ toast: jest.fn() }),
}));

describe("Progress Hooks Interface Verification", () => {
	const contentId = "test-content-123";

	it("useCourseProgress has standard interface", () => {
		const { result } = renderHook(() => useCourseProgress(contentId));

		// Verify interface structure
		expect(result.current).toHaveProperty("progress");
		expect(result.current).toHaveProperty("toggleCompletion");
		expect(result.current).toHaveProperty("isCompleted");
		expect(result.current).toHaveProperty("batchUpdate");
		expect(result.current).toHaveProperty("loading");
		expect(result.current).toHaveProperty("error");
		expect(result.current).toHaveProperty("refetch");
		expect(result.current).toHaveProperty("clearError");

		// Verify progress structure
		expect(result.current.progress).toHaveProperty("percentage");
		expect(result.current.progress).toHaveProperty("totalItems");
		expect(result.current.progress).toHaveProperty("completedItems");
		expect(result.current.progress).toHaveProperty("items");

		// Verify function types
		expect(typeof result.current.toggleCompletion).toBe("function");
		expect(typeof result.current.isCompleted).toBe("function");
		expect(typeof result.current.batchUpdate).toBe("function");
		expect(typeof result.current.refetch).toBe("function");
		expect(typeof result.current.clearError).toBe("function");
	});

	it("useVideoProgress has standard interface", () => {
		const { result } = renderHook(() => useVideoProgress(contentId));

		// Verify interface structure
		expect(result.current).toHaveProperty("progress");
		expect(result.current).toHaveProperty("toggleCompletion");
		expect(result.current).toHaveProperty("isCompleted");
		expect(result.current).toHaveProperty("batchUpdate");
		expect(result.current).toHaveProperty("loading");
		expect(result.current).toHaveProperty("error");
		expect(result.current).toHaveProperty("refetch");
		expect(result.current).toHaveProperty("clearError");

		// Verify progress structure
		expect(result.current.progress).toHaveProperty("percentage");
		expect(result.current.progress).toHaveProperty("totalItems");
		expect(result.current.progress).toHaveProperty("completedItems");
		expect(result.current.progress).toHaveProperty("items");
	});

	it("useBookProgress has standard interface", () => {
		const { result } = renderHook(() => useBookProgress(contentId));

		// Verify interface structure
		expect(result.current).toHaveProperty("progress");
		expect(result.current).toHaveProperty("toggleCompletion");
		expect(result.current).toHaveProperty("isCompleted");
		expect(result.current).toHaveProperty("batchUpdate");
		expect(result.current).toHaveProperty("loading");
		expect(result.current).toHaveProperty("error");
		expect(result.current).toHaveProperty("refetch");
		expect(result.current).toHaveProperty("clearError");

		// Verify progress structure
		expect(result.current.progress).toHaveProperty("percentage");
		expect(result.current.progress).toHaveProperty("totalItems");
		expect(result.current.progress).toHaveProperty("completedItems");
		expect(result.current.progress).toHaveProperty("items");
	});

	it("all hooks have identical interface shapes", () => {
		const courseHook = renderHook(() => useCourseProgress(contentId));
		const videoHook = renderHook(() => useVideoProgress(contentId));
		const bookHook = renderHook(() => useBookProgress(contentId));

		const courseKeys = Object.keys(courseHook.result.current).sort();
		const videoKeys = Object.keys(videoHook.result.current).sort();
		const bookKeys = Object.keys(bookHook.result.current).sort();

		// All should have same keys
		expect(courseKeys).toEqual(videoKeys);
		expect(videoKeys).toEqual(bookKeys);

		// Progress object should have same shape
		const courseProgressKeys = Object.keys(
			courseHook.result.current.progress,
		).sort();
		const videoProgressKeys = Object.keys(
			videoHook.result.current.progress,
		).sort();
		const bookProgressKeys = Object.keys(
			bookHook.result.current.progress,
		).sort();

		expect(courseProgressKeys).toEqual(videoProgressKeys);
		expect(videoProgressKeys).toEqual(bookProgressKeys);
	});
});
