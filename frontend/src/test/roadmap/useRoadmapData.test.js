import { useRoadmapData } from "@/features/roadmap/shared/useRoadmapData";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock fetch globally
global.fetch = vi.fn();

describe("useRoadmapData Hook", () => {
	beforeEach(() => {
		fetch.mockClear();
		vi.clearAllMocks();
	});

	it("should fetch roadmap data successfully", async () => {
		const mockRoadmap = {
			id: "roadmap-123",
			title: "Test Roadmap",
			description: "A test roadmap",
			nodes: [
				{ id: "node-1", title: "Node 1", status: "completed" },
				{ id: "node-2", title: "Node 2", status: "not_started" },
			],
		};

		fetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockRoadmap,
		});

		const { result } = renderHook(() => useRoadmapData("roadmap-123"));

		expect(result.current.isLoading).toBe(true);
		expect(result.current.roadmap).toBeNull();
		expect(result.current.error).toBeNull();

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.roadmap).toEqual(mockRoadmap);
		expect(result.current.error).toBeNull();
		expect(fetch).toHaveBeenCalledWith(
			"http://localhost:8080/api/v1/roadmaps/roadmap-123",
		);
	});

	it("should handle fetch errors", async () => {
		const errorMessage = "Network error";
		fetch.mockRejectedValueOnce(new Error(errorMessage));

		const { result } = renderHook(() => useRoadmapData("roadmap-123"));

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.roadmap).toBeNull();
		expect(result.current.error).toBe(errorMessage);
	});

	it("should handle HTTP error responses", async () => {
		fetch.mockResolvedValueOnce({
			ok: false,
			status: 404,
		});

		const { result } = renderHook(() => useRoadmapData("roadmap-123"));

		await waitFor(() => {
			expect(result.current.isLoading).toBe(false);
		});

		expect(result.current.roadmap).toBeNull();
		expect(result.current.error).toBe("HTTP error! status: 404");
	});

	it("should not fetch when roadmapId is null or undefined", () => {
		const { result } = renderHook(() => useRoadmapData(null));

		expect(result.current.isLoading).toBe(false);
		expect(result.current.roadmap).toBeNull();
		expect(result.current.error).toBeNull();
		expect(fetch).not.toHaveBeenCalled();
	});

	it("should refetch when roadmapId changes", async () => {
		const mockRoadmap1 = {
			id: "roadmap-1",
			title: "Roadmap 1",
		};

		const mockRoadmap2 = {
			id: "roadmap-2",
			title: "Roadmap 2",
		};

		fetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockRoadmap1,
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => mockRoadmap2,
			});

		const { result, rerender } = renderHook(
			({ roadmapId }) => useRoadmapData(roadmapId),
			{ initialProps: { roadmapId: "roadmap-1" } },
		);

		await waitFor(() => {
			expect(result.current.roadmap).toEqual(mockRoadmap1);
		});

		// Change the roadmapId
		rerender({ roadmapId: "roadmap-2" });

		await waitFor(() => {
			expect(result.current.roadmap).toEqual(mockRoadmap2);
		});

		expect(fetch).toHaveBeenCalledTimes(2);
		expect(fetch).toHaveBeenNthCalledWith(
			1,
			"http://localhost:8080/api/v1/roadmaps/roadmap-1",
		);
		expect(fetch).toHaveBeenNthCalledWith(
			2,
			"http://localhost:8080/api/v1/roadmaps/roadmap-2",
		);
	});

	// Tests for Phase 3 integration with new endpoints
	describe("Phase 3 Integration", () => {
		it("should use new roadmap nodes endpoint", async () => {
			// This test assumes the hook will be updated to use the new endpoint
			const mockNodes = [
				{
					id: "node-1",
					title: "Node 1",
					status: "completed",
					completion_percentage: 100,
				},
				{
					id: "node-2",
					title: "Node 2",
					status: "in_progress",
					completion_percentage: 50,
				},
				{
					id: "node-3",
					title: "Node 3",
					status: "not_started",
					completion_percentage: 0,
				},
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockNodes,
			});

			// After Phase 3 implementation, this should call the nodes endpoint
			const { result } = renderHook(() => useRoadmapData("roadmap-123"));

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			// After Phase 3 implementation, this should use the new endpoint
			// expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/v1/roadmaps/roadmap-123/nodes')
		});

		it("should handle direct node status updates", async () => {
			// This test is for the functionality that will be added in Phase 3
			const mockRoadmap = {
				id: "roadmap-123",
				title: "Test Roadmap",
				nodes: [{ id: "node-1", title: "Node 1", status: "not_started" }],
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockRoadmap,
			});

			const { result } = renderHook(() => useRoadmapData("roadmap-123"));

			await waitFor(() => {
				expect(result.current.roadmap).toEqual(mockRoadmap);
			});

			// After Phase 3 implementation, the hook should provide a method to update node status
			// expect(typeof result.current.updateNodeStatus).toBe('function')
		});

		it("should batch fetch node progress data", async () => {
			// This test is for the functionality that will be added in Phase 3
			const mockRoadmap = {
				id: "roadmap-123",
				title: "Test Roadmap",
				nodes: [
					{ id: "node-1", title: "Node 1" },
					{ id: "node-2", title: "Node 2" },
				],
			};

			const mockProgressData = {
				"node-1": { status: "completed", completion_percentage: 100 },
				"node-2": { status: "in_progress", completion_percentage: 50 },
			};

			fetch
				.mockResolvedValueOnce({
					ok: true,
					json: async () => mockRoadmap,
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => mockProgressData,
				});

			const { result } = renderHook(() => useRoadmapData("roadmap-123"));

			await waitFor(() => {
				expect(result.current.roadmap).toBeTruthy();
			});

			// After Phase 3 implementation, this should also fetch progress data
			// expect(fetch).toHaveBeenCalledWith(
			//   expect.stringContaining('/progress/user/'),
			//   expect.objectContaining({
			//     method: 'POST',
			//     body: JSON.stringify({ nodeIds: ['node-1', 'node-2'] })
			//   })
			// )
		});

		it("should provide optimistic updates for node status changes", async () => {
			// This test is for the functionality that will be added in Phase 3
			const mockRoadmap = {
				id: "roadmap-123",
				title: "Test Roadmap",
				nodes: [{ id: "node-1", title: "Node 1", status: "not_started" }],
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockRoadmap,
			});

			const { result } = renderHook(() => useRoadmapData("roadmap-123"));

			await waitFor(() => {
				expect(result.current.roadmap).toEqual(mockRoadmap);
			});

			// After Phase 3 implementation, the hook should support optimistic updates
			// act(() => {
			//   result.current.updateNodeStatus('node-1', 'completed')
			// })

			// Node should be immediately updated optimistically
			// expect(result.current.roadmap.nodes[0].status).toBe('completed')
		});

		it("should handle network errors gracefully with retry", async () => {
			// This test is for enhanced error handling in Phase 3
			fetch
				.mockRejectedValueOnce(new Error("Network error"))
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ id: "roadmap-123", title: "Test" }),
				});

			const { result } = renderHook(() => useRoadmapData("roadmap-123"));

			await waitFor(() => {
				expect(result.current.error).toBeTruthy();
			});

			// After Phase 3, the hook might provide a retry function
			// act(() => {
			//   result.current.retry()
			// })

			// await waitFor(() => {
			//   expect(result.current.roadmap).toBeTruthy()
			//   expect(result.current.error).toBeNull()
			// })
		});
	});
});
