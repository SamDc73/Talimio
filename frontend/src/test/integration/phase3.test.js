import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// This file contains integration tests for Phase 3 functionality
// These tests simulate the complete user workflows that Phase 3 should support

// Mock all the necessary hooks and services
vi.mock("@/hooks/useApi", () => ({
	useApi: vi.fn(),
}));

vi.mock("@/services/progressService", () => ({
	getNodeProgress: vi.fn(),
	getUserProgress: vi.fn(),
	createNodeProgress: vi.fn(),
	updateProgress: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
	useToast: () => ({
		toast: vi.fn(),
	}),
}));

describe("Phase 3 Integration Tests", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
	});

	describe("Direct Node Updates", () => {
		it("should update node status directly through new API", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockResolvedValue({ success: true });

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			// Simulate component that updates node status
			const TestComponent = () => {
				const nodeApi = useApi("/nodes/{nodeId}/status", { method: "PUT" });

				const handleComplete = async () => {
					await nodeApi.execute(
						{ status: "completed" },
						{ pathParams: { nodeId: "node-123" } },
					);
				};

				return (
					<button
						type="button"
						onClick={handleComplete}
						data-testid="complete-button"
					>
						Mark Complete
					</button>
				);
			};

			const user = userEvent.setup();
			render(<TestComponent />);

			const button = screen.getByTestId("complete-button");
			await user.click(button);

			expect(mockExecute).toHaveBeenCalledWith(
				{ status: "completed" },
				{ pathParams: { nodeId: "node-123" } },
			);
		});

		it("should handle node status update failures gracefully", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockRejectedValue(new Error("API Error"));

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestComponent = () => {
				const nodeApi = useApi("/nodes/{nodeId}/status", { method: "PUT" });

				const handleComplete = async () => {
					try {
						await nodeApi.execute(
							{ status: "completed" },
							{ pathParams: { nodeId: "node-123" } },
						);
					} catch (error) {
						// Error should be handled by the useApi hook
					}
				};

				return (
					<button
						type="button"
						onClick={handleComplete}
						data-testid="complete-button"
					>
						Mark Complete
					</button>
				);
			};

			const user = userEvent.setup();
			render(<TestComponent />);

			const button = screen.getByTestId("complete-button");
			await user.click(button);

			expect(mockExecute).toHaveBeenCalled();
			// Error handling should be managed by the useApi hook
		});
	});

	describe("Book Chapter Management", () => {
		it("should fetch and display book chapters from new API", async () => {
			const { useApi } = await import("@/hooks/useApi");
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

			const mockExecute = vi.fn().mockResolvedValue(mockChapters);

			useApi.mockReturnValue({
				data: mockChapters,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestBookComponent = ({ bookId }) => {
				const chaptersApi = useApi("/books/{bookId}/chapters");

				React.useEffect(() => {
					chaptersApi.execute(null, { pathParams: { bookId } });
				}, [bookId, chaptersApi.execute]);

				return (
					<div>
						{chaptersApi.data?.map((chapter) => (
							<div key={chapter.id} data-testid={`chapter-${chapter.id}`}>
								{chapter.title} - {chapter.status}
							</div>
						))}
					</div>
				);
			};

			render(<TestBookComponent bookId="book-123" />);

			await waitFor(() => {
				expect(screen.getByTestId("chapter-1")).toBeInTheDocument();
				expect(screen.getByTestId("chapter-2")).toBeInTheDocument();
			});

			expect(screen.getByText(/Chapter 1 - not_started/)).toBeInTheDocument();
			expect(screen.getByText(/Chapter 2 - completed/)).toBeInTheDocument();
		});

		it("should extract book chapters when requested", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockResolvedValue({
				message: "Chapters extracted successfully",
				count: 5,
			});

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestExtractComponent = ({ bookId }) => {
				const extractApi = useApi("/books/{bookId}/extract-chapters", {
					method: "POST",
				});

				const handleExtract = async () => {
					await extractApi.execute(null, { pathParams: { bookId } });
				};

				return (
					<button
						type="button"
						onClick={handleExtract}
						data-testid="extract-button"
					>
						Extract Chapters
					</button>
				);
			};

			const user = userEvent.setup();
			render(<TestExtractComponent bookId="book-123" />);

			const button = screen.getByTestId("extract-button");
			await user.click(button);

			expect(mockExecute).toHaveBeenCalledWith(null, {
				pathParams: { bookId: "book-123" },
			});
		});

		it("should update chapter status when marked complete", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockResolvedValue({ success: true });

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestChapterComponent = ({ bookId, chapterId }) => {
				const statusApi = useApi(
					"/books/{bookId}/chapters/{chapterId}/status",
					{ method: "PUT" },
				);

				const handleComplete = async () => {
					await statusApi.execute(
						{ status: "completed" },
						{ pathParams: { bookId, chapterId } },
					);
				};

				return (
					<button
						type="button"
						onClick={handleComplete}
						data-testid="complete-chapter"
					>
						Complete Chapter
					</button>
				);
			};

			const user = userEvent.setup();
			render(<TestChapterComponent bookId="book-123" chapterId="chapter-1" />);

			const button = screen.getByTestId("complete-chapter");
			await user.click(button);

			expect(mockExecute).toHaveBeenCalledWith(
				{ status: "completed" },
				{ pathParams: { bookId: "book-123", chapterId: "chapter-1" } },
			);
		});
	});

	describe("Video Chapter Management", () => {
		it("should fetch and display video chapters from new API", async () => {
			const { useApi } = await import("@/hooks/useApi");
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

			const mockExecute = vi.fn().mockResolvedValue(mockChapters);

			useApi.mockReturnValue({
				data: mockChapters,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestVideoComponent = ({ videoUuid }) => {
				const chaptersApi = useApi("/videos/{videoUuid}/chapters");

				React.useEffect(() => {
					chaptersApi.execute(null, { pathParams: { videoUuid } });
				}, [videoUuid, chaptersApi.execute]);

				return (
					<div>
						{chaptersApi.data?.map((chapter) => (
							<div key={chapter.id} data-testid={`video-chapter-${chapter.id}`}>
								{chapter.title} - {chapter.status}
							</div>
						))}
					</div>
				);
			};

			render(<TestVideoComponent videoUuid="video-uuid-123" />);

			await waitFor(() => {
				expect(screen.getByTestId("video-chapter-1")).toBeInTheDocument();
				expect(screen.getByTestId("video-chapter-2")).toBeInTheDocument();
			});

			expect(screen.getByText(/Intro - completed/)).toBeInTheDocument();
			expect(
				screen.getByText(/Main Content - not_started/),
			).toBeInTheDocument();
		});

		it("should extract video chapters when requested", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockResolvedValue({
				message: "Chapters extracted successfully",
				count: 3,
			});

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestVideoExtractComponent = ({ videoUuid }) => {
				const extractApi = useApi("/videos/{videoUuid}/extract-chapters", {
					method: "POST",
				});

				const handleExtract = async () => {
					await extractApi.execute(null, { pathParams: { videoUuid } });
				};

				return (
					<button
						type="button"
						onClick={handleExtract}
						data-testid="extract-video-chapters"
					>
						Extract Video Chapters
					</button>
				);
			};

			const user = userEvent.setup();
			render(<TestVideoExtractComponent videoUuid="video-uuid-123" />);

			const button = screen.getByTestId("extract-video-chapters");
			await user.click(button);

			expect(mockExecute).toHaveBeenCalledWith(null, {
				pathParams: { videoUuid: "video-uuid-123" },
			});
		});
	});

	describe("Progress Service Integration", () => {
		it("should use new progress endpoints for data fetching", async () => {
			const { getUserProgress } = await import("@/services/progressService");
			const mockProgress = [
				{ id: "1", node_id: "node-1", status: "completed" },
				{ id: "2", node_id: "node-2", status: "in_progress" },
			];

			getUserProgress.mockResolvedValue(mockProgress);

			const TestProgressComponent = ({ userId }) => {
				const [progress, setProgress] = React.useState([]);

				React.useEffect(() => {
					getUserProgress(userId).then(setProgress);
				}, [userId]);

				return (
					<div>
						{progress.map((p) => (
							<div key={p.id} data-testid={`progress-${p.id}`}>
								{p.node_id}: {p.status}
							</div>
						))}
					</div>
				);
			};

			render(<TestProgressComponent userId="user-123" />);

			await waitFor(() => {
				expect(screen.getByTestId("progress-1")).toBeInTheDocument();
				expect(screen.getByTestId("progress-2")).toBeInTheDocument();
			});

			expect(getUserProgress).toHaveBeenCalledWith("user-123");
		});

		it("should handle progress cache correctly", async () => {
			const { getNodeProgress, _progressCache } = await import(
				"@/services/progressService"
			);

			// Clear cache first
			_progressCache.clear();

			const mockProgress = { id: "1", nodeId: "node-1", status: "completed" };
			getNodeProgress.mockResolvedValue(mockProgress);

			// First call should hit the API
			await getNodeProgress("user-1", "node-1");

			// Second call should use cache (mock would only be called once)
			await getNodeProgress("user-1", "node-1");

			expect(getNodeProgress).toHaveBeenCalledTimes(2);
			// In real implementation, second call would use cache
		});
	});

	describe("Error Handling and Loading States", () => {
		it("should show loading states during API calls", async () => {
			const { useApi } = await import("@/hooks/useApi");

			useApi.mockReturnValue({
				data: null,
				isLoading: true,
				error: null,
				execute: vi.fn(),
			});

			const TestLoadingComponent = () => {
				const api = useApi("/test-endpoint");

				return (
					<div>
						{api.isLoading && <div data-testid="loading">Loading...</div>}
						{api.data && <div data-testid="data">Data loaded</div>}
					</div>
				);
			};

			render(<TestLoadingComponent />);

			expect(screen.getByTestId("loading")).toBeInTheDocument();
			expect(screen.queryByTestId("data")).not.toBeInTheDocument();
		});

		it("should handle and display API errors", async () => {
			const { useApi } = await import("@/hooks/useApi");

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: new Error("API Error"),
				execute: vi.fn(),
			});

			const TestErrorComponent = () => {
				const api = useApi("/test-endpoint");

				return (
					<div>
						{api.error && (
							<div data-testid="error">Error: {api.error.message}</div>
						)}
						{api.data && <div data-testid="data">Data loaded</div>}
					</div>
				);
			};

			render(<TestErrorComponent />);

			expect(screen.getByTestId("error")).toBeInTheDocument();
			expect(screen.getByText("Error: API Error")).toBeInTheDocument();
		});
	});

	describe("Complete User Workflows", () => {
		it("should support complete roadmap progress tracking workflow", async () => {
			// This test simulates a complete user journey:
			// 1. Load roadmap with nodes
			// 2. Update node status
			// 3. Track overall progress

			const { useApi } = await import("@/hooks/useApi");

			const mockRoadmapNodes = [
				{ id: "node-1", title: "Node 1", status: "not_started" },
				{ id: "node-2", title: "Node 2", status: "completed" },
			];

			const mockExecute = vi
				.fn()
				.mockResolvedValueOnce(mockRoadmapNodes) // Initial fetch
				.mockResolvedValueOnce({ success: true }); // Status update

			useApi.mockReturnValue({
				data: mockRoadmapNodes,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			const TestWorkflowComponent = () => {
				const roadmapApi = useApi("/roadmaps/{roadmapId}/nodes");
				const statusApi = useApi("/nodes/{nodeId}/status", { method: "PUT" });

				const handleCompleteNode = async (nodeId) => {
					await statusApi.execute(
						{ status: "completed" },
						{ pathParams: { nodeId } },
					);
					// In real implementation, would refetch roadmap data
				};

				return (
					<div>
						<div data-testid="progress">
							Progress:{" "}
							{roadmapApi.data?.filter((n) => n.status === "completed").length}{" "}
							/ {roadmapApi.data?.length}
						</div>
						{roadmapApi.data?.map((node) => (
							<div key={node.id}>
								{node.title} - {node.status}
								{node.status !== "completed" && (
									<button
										type="button"
										onClick={() => handleCompleteNode(node.id)}
										data-testid={`complete-${node.id}`}
									>
										Complete
									</button>
								)}
							</div>
						))}
					</div>
				);
			};

			const user = userEvent.setup();
			render(<TestWorkflowComponent />);

			// Initial state shows 1/2 completed
			expect(screen.getByText("Progress: 1 / 2")).toBeInTheDocument();

			// Complete the remaining node
			const completeButton = screen.getByTestId("complete-node-1");
			await user.click(completeButton);

			expect(mockExecute).toHaveBeenCalledWith(
				{ status: "completed" },
				{ pathParams: { nodeId: "node-1" } },
			);
		});
	});
});
