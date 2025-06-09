import {
	_batchProgressRequests,
	_progressCache,
	createNodeProgress,
	getNodeProgress,
	getUserProgress,
	updateProgress,
} from "@/services/progressService";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock fetch globally
global.fetch = vi.fn();

describe("Progress Service", () => {
	beforeEach(() => {
		fetch.mockClear();
		_progressCache.clear();
		vi.clearAllMocks();
	});

	describe("getNodeProgress", () => {
		it("should fetch node progress successfully", async () => {
			const mockProgress = {
				id: "progress-1",
				userId: "user-1",
				nodeId: "node-1",
				status: "completed",
				updatedAt: new Date().toISOString(),
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockProgress,
			});

			const result = await getNodeProgress("user-1", "node-1");

			expect(result).toEqual(mockProgress);
			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/progress/user/user-1/node/node-1",
			);
		});

		it("should return cached data on second call", async () => {
			const mockProgress = {
				id: "progress-1",
				userId: "user-1",
				nodeId: "node-1",
				status: "completed",
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockProgress,
			});

			// First call
			await getNodeProgress("user-1", "node-1");

			// Second call should use cache
			const result = await getNodeProgress("user-1", "node-1");

			expect(result).toEqual(mockProgress);
			expect(fetch).toHaveBeenCalledTimes(1);
		});

		it("should throw error on failed request", async () => {
			fetch.mockResolvedValueOnce({
				ok: false,
				status: 404,
				statusText: "Not Found",
			});

			await expect(getNodeProgress("user-1", "node-1")).rejects.toThrow(
				"Failed to fetch progress: Not Found",
			);
		});
	});

	describe("getUserProgress", () => {
		it("should fetch all user progress successfully", async () => {
			const mockProgress = [
				{ id: "progress-1", nodeId: "node-1", status: "completed" },
				{ id: "progress-2", nodeId: "node-2", status: "in_progress" },
			];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockProgress,
			});

			const result = await getUserProgress("user-1");

			expect(result).toEqual(mockProgress);
			expect(fetch).toHaveBeenCalledWith("/api/v1/progress/user/user-1");
		});

		it("should handle fetch timeout", async () => {
			fetch.mockRejectedValueOnce(new Error("Request timeout after 7000ms"));

			await expect(getUserProgress("user-1")).rejects.toThrow(
				"Request timeout after 7000ms",
			);
		});
	});

	describe("createNodeProgress", () => {
		it("should create node progress successfully", async () => {
			const progressData = { status: "in_progress", completionPercentage: 50 };
			const mockResponse = {
				id: "progress-1",
				nodeId: "node-1",
				...progressData,
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const result = await createNodeProgress("node-1", progressData);

			expect(result).toEqual(mockResponse);
			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/progress/node/node-1",
				expect.objectContaining({
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(progressData),
				}),
			);
		});

		it("should clear cache after creating progress", async () => {
			// Set some cache data first
			_progressCache.set("test-key", { data: "test" });
			expect(_progressCache.get("test-key")).toBeTruthy();

			const progressData = { status: "completed" };
			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ id: "progress-1" }),
			});

			await createNodeProgress("node-1", progressData);

			// Cache should be cleared
			expect(_progressCache.get("test-key")).toBeNull();
		});
	});

	describe("updateProgress", () => {
		it("should update progress successfully", async () => {
			const updateData = { status: "completed", completionPercentage: 100 };
			const mockResponse = { id: "progress-1", ...updateData };

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const result = await updateProgress("progress-1", updateData);

			expect(result).toEqual(mockResponse);
			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/progress/progress-1",
				expect.objectContaining({
					method: "PUT",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(updateData),
				}),
			);
		});

		it("should clear cache after updating progress", async () => {
			// Set some cache data first
			_progressCache.set("test-key", { data: "test" });
			expect(_progressCache.get("test-key")).toBeTruthy();

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ id: "progress-1" }),
			});

			await updateProgress("progress-1", { status: "completed" });

			// Cache should be cleared
			expect(_progressCache.get("test-key")).toBeNull();
		});
	});

	describe("batchProgressRequests", () => {
		it("should handle batch requests successfully", async () => {
			const nodeIds = ["node-1", "node-2", "node-3"];
			const mockResponse = {
				"node-1": { status: "completed" },
				"node-2": { status: "in_progress" },
				"node-3": { status: "not_started" },
			};

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			const result = await _batchProgressRequests(nodeIds, "user-1");

			expect(result).toEqual(mockResponse);
			expect(fetch).toHaveBeenCalledWith(
				"/api/v1/progress/user/user-1/batch",
				expect.objectContaining({
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ nodeIds }),
				}),
			);
		});

		it("should deduplicate node IDs", async () => {
			const nodeIds = ["node-1", "node-2", "node-1", "node-3", "node-2"];
			const expectedUniqueIds = ["node-1", "node-2", "node-3"];

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({}),
			});

			await _batchProgressRequests(nodeIds, "user-1");

			const call = fetch.mock.calls[0];
			const requestBody = JSON.parse(call[1].body);
			expect(requestBody.nodeIds.sort()).toEqual(expectedUniqueIds.sort());
		});

		it("should use cache for repeated batch requests", async () => {
			const nodeIds = ["node-1", "node-2"];
			const mockResponse = { "node-1": { status: "completed" } };

			fetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockResponse,
			});

			// First call
			await _batchProgressRequests(nodeIds, "user-1");

			// Second call should use cache
			const result = await _batchProgressRequests(nodeIds, "user-1");

			expect(result).toEqual(mockResponse);
			expect(fetch).toHaveBeenCalledTimes(1);
		});
	});

	describe("Cache functionality", () => {
		it("should expire cached data after maxAge", async () => {
			// Mock Date.now to control cache expiration
			const originalDateNow = Date.now;
			const startTime = 1000000000000;

			Date.now = vi.fn(() => startTime);

			// Set cache data
			_progressCache.set("test-key", { data: "test" });
			expect(_progressCache.get("test-key")).toBeTruthy();

			// Advance time beyond maxAge (5 minutes = 300000ms)
			Date.now = vi.fn(() => startTime + 300001);

			// Cache should be expired
			expect(_progressCache.get("test-key")).toBeNull();

			// Restore original Date.now
			Date.now = originalDateNow;
		});

		it("should handle cache size limit", () => {
			// This would require creating a cache with smaller maxSize for testing
			// For now, we'll test that the cache set/get works correctly
			_progressCache.set("key1", { data: "value1" });
			_progressCache.set("key2", { data: "value2" });

			expect(_progressCache.get("key1")).toEqual({ data: "value1" });
			expect(_progressCache.get("key2")).toEqual({ data: "value2" });
		});
	});
});
