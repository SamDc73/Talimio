import { useApi } from "@/hooks/useApi";
import { render, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the toast hook
vi.mock("@/hooks/use-toast", () => ({
	useToast: () => ({
		toast: vi.fn(),
	}),
}));

// Mock fetch globally
global.fetch = vi.fn();

describe("useApi Hook", () => {
	beforeEach(() => {
		fetch.mockClear();
		vi.clearAllMocks();
	});

	it("should handle GET requests correctly", async () => {
		const mockData = { id: "1", name: "Test" };
		fetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockData,
		});

		const { result } = renderHook(() => useApi("/test-endpoint"));

		await waitFor(async () => {
			const response = await result.current.execute();
			expect(response).toEqual(mockData);
		});

		expect(fetch).toHaveBeenCalledWith(
			"/api/v1/test-endpoint",
			expect.objectContaining({
				method: "GET",
				headers: {
					"Content-Type": "application/json",
				},
			}),
		);
	});

	it("should handle POST requests with body", async () => {
		const mockData = { id: "1", created: true };
		const requestBody = { name: "New Item" };

		fetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockData,
		});

		const { result } = renderHook(() =>
			useApi("/test-endpoint", { method: "POST" }),
		);

		await waitFor(async () => {
			const response = await result.current.execute(requestBody);
			expect(response).toEqual(mockData);
		});

		expect(fetch).toHaveBeenCalledWith(
			"/api/v1/test-endpoint",
			expect.objectContaining({
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(requestBody),
			}),
		);
	});

	it("should handle path parameters", async () => {
		const mockData = { id: "123", name: "Test" };
		fetch.mockResolvedValueOnce({
			ok: true,
			json: async () => mockData,
		});

		const { result } = renderHook(() => useApi("/nodes/{nodeId}"));

		await waitFor(async () => {
			const response = await result.current.execute(null, {
				pathParams: { nodeId: "123" },
			});
			expect(response).toEqual(mockData);
		});

		expect(fetch).toHaveBeenCalledWith("/api/v1/nodes/123", expect.any(Object));
	});

	it("should handle error responses", async () => {
		const errorData = { message: "Not found" };
		fetch.mockResolvedValueOnce({
			ok: false,
			status: 404,
			statusText: "Not Found",
			json: async () => errorData,
		});

		const { result } = renderHook(() => useApi("/test-endpoint"));

		await waitFor(async () => {
			try {
				await result.current.execute();
			} catch (error) {
				expect(error.status).toBe(404);
				expect(error.data).toEqual(errorData);
			}
		});
	});
});

// Tests for new Phase 3 endpoints that need to be added
describe("Phase 3 API Endpoints", () => {
	beforeEach(() => {
		fetch.mockClear();
		vi.clearAllMocks();
	});

	describe("Direct Node Access", () => {
		it("should get node by ID", async () => {
			const mockNode = {
				id: "node-123",
				title: "Test Node",
				status: "not_started",
				completion_percentage: 0,
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockNode,
			});

			const { result } = renderHook(() => useApi("/nodes/{nodeId}"));

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { nodeId: "node-123" },
				});
				expect(response).toEqual(mockNode);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/nodes/node-123",
				expect.any(Object),
			);
		});

		it("should update node status", async () => {
			const statusUpdate = { status: "completed" };
			const mockResponse = { success: true };

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const { result } = renderHook(() =>
				useApi("/nodes/{nodeId}/status", { method: "PUT" }),
			);

			await waitFor(async () => {
				const response = await result.current.execute(statusUpdate, {
					pathParams: { nodeId: "node-123" },
				});
				expect(response).toEqual(mockResponse);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/nodes/node-123/status",
				expect.objectContaining({
					method: "PUT",
					body: JSON.stringify(statusUpdate),
				}),
			);
		});
	});

	describe("Book Chapter Endpoints", () => {
		it("should get book chapters", async () => {
			const mockChapters = [
				{
					id: 1,
					title: "Chapter 1",
					start_page: 1,
					end_page: 10,
					status: "not_started",
				},
				{
					id: 2,
					title: "Chapter 2",
					start_page: 11,
					end_page: 20,
					status: "completed",
				},
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockChapters,
			});

			const { result } = renderHook(() => useApi("/books/{bookId}/chapters"));

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { bookId: "book-123" },
				});
				expect(response).toEqual(mockChapters);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/books/book-123/chapters",
				expect.any(Object),
			);
		});

		it("should update chapter status", async () => {
			const statusUpdate = { status: "completed" };
			const mockResponse = { success: true };

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const { result } = renderHook(() =>
				useApi("/books/{bookId}/chapters/{chapterId}/status", {
					method: "PUT",
				}),
			);

			await waitFor(async () => {
				const response = await result.current.execute(statusUpdate, {
					pathParams: { bookId: "book-123", chapterId: "chapter-1" },
				});
				expect(response).toEqual(mockResponse);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/books/book-123/chapters/chapter-1/status",
				expect.objectContaining({
					method: "PUT",
					body: JSON.stringify(statusUpdate),
				}),
			);
		});

		it("should extract book chapters", async () => {
			const mockResponse = {
				message: "Chapters extracted successfully",
				count: 5,
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const { result } = renderHook(() =>
				useApi("/books/{bookId}/extract-chapters", { method: "POST" }),
			);

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { bookId: "book-123" },
				});
				expect(response).toEqual(mockResponse);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/books/book-123/extract-chapters",
				expect.any(Object),
			);
		});
	});

	describe("Video Chapter Endpoints", () => {
		it("should get video chapters", async () => {
			const mockChapters = [
				{
					id: 1,
					title: "Intro",
					start_time: 0,
					end_time: 60,
					status: "completed",
				},
				{
					id: 2,
					title: "Main Content",
					start_time: 60,
					end_time: 300,
					status: "not_started",
				},
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockChapters,
			});

			const { result } = renderHook(() =>
				useApi("/videos/{videoUuid}/chapters"),
			);

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { videoUuid: "video-uuid-123" },
				});
				expect(response).toEqual(mockChapters);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/videos/video-uuid-123/chapters",
				expect.any(Object),
			);
		});

		it("should update video chapter status", async () => {
			const statusUpdate = { status: "completed" };
			const mockResponse = { success: true };

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const { result } = renderHook(() =>
				useApi("/videos/{videoUuid}/chapters/{chapterId}/status", {
					method: "PUT",
				}),
			);

			await waitFor(async () => {
				const response = await result.current.execute(statusUpdate, {
					pathParams: { videoUuid: "video-uuid-123", chapterId: "chapter-1" },
				});
				expect(response).toEqual(mockResponse);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/videos/video-uuid-123/chapters/chapter-1/status",
				expect.objectContaining({
					method: "PUT",
					body: JSON.stringify(statusUpdate),
				}),
			);
		});

		it("should extract video chapters", async () => {
			const mockResponse = {
				message: "Chapters extracted successfully",
				count: 3,
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const { result } = renderHook(() =>
				useApi("/videos/{videoUuid}/extract-chapters", { method: "POST" }),
			);

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { videoUuid: "video-uuid-123" },
				});
				expect(response).toEqual(mockResponse);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/videos/video-uuid-123/extract-chapters",
				expect.any(Object),
			);
		});
	});

	describe("Progress Endpoints", () => {
		it("should get user progress", async () => {
			const mockProgress = [
				{ id: "1", node_id: "node-1", status: "completed" },
				{ id: "2", node_id: "node-2", status: "in_progress" },
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockProgress,
			});

			const { result } = renderHook(() => useApi("/progress/user/{userId}"));

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { userId: "user-123" },
				});
				expect(response).toEqual(mockProgress);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/progress/user/user-123",
				expect.any(Object),
			);
		});

		it("should get roadmap nodes", async () => {
			const mockNodes = [
				{ id: "node-1", title: "Node 1", status: "completed" },
				{ id: "node-2", title: "Node 2", status: "not_started" },
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockNodes,
			});

			const { result } = renderHook(() =>
				useApi("/roadmaps/{roadmapId}/nodes"),
			);

			await waitFor(async () => {
				const response = await result.current.execute(null, {
					pathParams: { roadmapId: "roadmap-123" },
				});
				expect(response).toEqual(mockNodes);
			});

			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/roadmaps/roadmap-123/nodes",
				expect.any(Object),
			);
		});
	});
});
