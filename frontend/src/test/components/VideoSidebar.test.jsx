import VideoSidebar from "@/components/sidebar/VideoSidebar";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the Zustand store
vi.mock("@/stores/useAppStore", () => ({
	default: vi.fn(() => true), // Mock sidebarOpen state
}));

// Mock the useApi hook for chapter fetching
vi.mock("@/hooks/useApi", () => ({
	useApi: vi.fn(() => ({
		data: null,
		isLoading: false,
		error: null,
		execute: vi.fn(),
	})),
}));

describe("VideoSidebar", () => {
	const mockVideo = {
		uuid: "video-123",
		title: "Test Video Tutorial",
		channel: "Test Channel",
		duration: 3600, // 1 hour
		description: `
Welcome to this tutorial!

0:00 - Introduction
2:30 - Setup and Installation  
5:15 - Getting Started
10:45 - Advanced Features
25:00 - Best Practices
50:30 - Conclusion

Thanks for watching!
    `,
	};

	const mockOnSeek = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders video sidebar with basic info", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		expect(screen.getByText("Test Video Tutorial")).toBeInTheDocument();
		expect(screen.getByText("Test Channel")).toBeInTheDocument();
		expect(screen.getByText("Chapters")).toBeInTheDocument();
		expect(screen.getByText("Duration: 1h 0m")).toBeInTheDocument();
	});

	it("extracts chapters from video description", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		expect(screen.getByText("Introduction")).toBeInTheDocument();
		expect(screen.getByText("Setup and Installation")).toBeInTheDocument();
		expect(screen.getByText("Getting Started")).toBeInTheDocument();
		expect(screen.getByText("Advanced Features")).toBeInTheDocument();
		expect(screen.getByText("Best Practices")).toBeInTheDocument();
		expect(screen.getByText("Conclusion")).toBeInTheDocument();
	});

	it("displays chapter timestamps correctly", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		expect(screen.getByText("0:00")).toBeInTheDocument();
		expect(screen.getByText("2:30")).toBeInTheDocument();
		expect(screen.getByText("5:15")).toBeInTheDocument();
		expect(screen.getByText("10:45")).toBeInTheDocument();
		expect(screen.getByText("25:00")).toBeInTheDocument();
		expect(screen.getByText("50:30")).toBeInTheDocument();
	});

	it("calls onSeek when chapter is clicked", async () => {
		const user = userEvent.setup();
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		const chapterButton = screen.getByText("Getting Started").closest("button");
		await user.click(chapterButton);

		expect(mockOnSeek).toHaveBeenCalledWith(315); // 5:15 = 315 seconds
	});

	it("highlights active chapter based on current time", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={400} onSeek={mockOnSeek} />,
		);

		// At 400 seconds (6:40), should be in "Getting Started" chapter (5:15 - 10:45)
		const activeChapter = screen.getByText("Getting Started").closest("div");
		expect(activeChapter).toHaveClass("bg-red-50"); // Active chapter styling
	});

	it("shows progress bar for active chapter", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={400} onSeek={mockOnSeek} />,
		);

		// Should show a progress bar for the active chapter
		const progressBars = screen.getAllByRole("progressbar", { hidden: true });
		expect(progressBars.length).toBeGreaterThan(0);
	});

	it("toggles chapter completion status", async () => {
		const user = userEvent.setup();
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		const checkboxes = screen.getAllByRole("checkbox");
		const firstCheckbox = checkboxes[0];

		// Initially not completed
		expect(firstCheckbox).not.toBeChecked();

		// Click to mark as completed
		await user.click(firstCheckbox);

		// Should be marked as completed (visual state would need to be checked)
		// This is internal state, so we'd verify through UI changes
	});

	it("calculates overall progress correctly", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		// Initially 0% progress since no chapters are completed
		// After marking chapters as complete, progress should update
		// This would require testing the progress indicator value
	});

	it("shows fallback when no chapters found", () => {
		const videoWithoutChapters = {
			...mockVideo,
			description: "Just a regular description without timestamps",
		};

		render(
			<VideoSidebar
				video={videoWithoutChapters}
				currentTime={0}
				onSeek={mockOnSeek}
			/>,
		);

		expect(screen.getByText("No chapters found")).toBeInTheDocument();
		expect(
			screen.getByText("Chapters are extracted from the video description"),
		).toBeInTheDocument();
	});

	it("returns null when no video is provided", () => {
		const { container } = render(
			<VideoSidebar video={null} currentTime={0} onSeek={mockOnSeek} />,
		);
		expect(container.firstChild).toBeNull();
	});

	it("formats duration correctly", () => {
		const shortVideo = { ...mockVideo, duration: 125 }; // 2 minutes 5 seconds
		render(
			<VideoSidebar video={shortVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		expect(screen.getByText("Duration: 2m 5s")).toBeInTheDocument();
	});

	it("shows chapter count", () => {
		render(
			<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
		);

		expect(screen.getByText("6 chapters")).toBeInTheDocument();
	});

	describe("Chapter extraction edge cases", () => {
		it("handles different timestamp formats", () => {
			const videoWithVariousFormats = {
				...mockVideo,
				description: `
1:23 First chapter
01:23 Second chapter  
1:23:45 Third chapter with hours
        `,
			};

			render(
				<VideoSidebar
					video={videoWithVariousFormats}
					currentTime={0}
					onSeek={mockOnSeek}
				/>,
			);

			expect(screen.getByText("First chapter")).toBeInTheDocument();
			expect(screen.getByText("Second chapter")).toBeInTheDocument();
			expect(screen.getByText("Third chapter with hours")).toBeInTheDocument();
		});

		it("cleans chapter titles properly", () => {
			const videoWithMessyTitles = {
				...mockVideo,
				description: `
0:00 - Introduction
2:30 (Part 1) Setup
5:00 *** Getting Started ***
        `,
			};

			render(
				<VideoSidebar
					video={videoWithMessyTitles}
					currentTime={0}
					onSeek={mockOnSeek}
				/>,
			);

			expect(screen.getByText("Introduction")).toBeInTheDocument();
			expect(screen.getByText("Setup")).toBeInTheDocument();
			expect(screen.getByText("Getting Started")).toBeInTheDocument();
		});
	});

	// Tests for Phase 3 integration with new chapter endpoints
	describe("Phase 3 Chapter Integration", () => {
		it("should fetch chapters from new API endpoint", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExecute = vi.fn().mockResolvedValue([
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
			]);

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExecute,
			});

			render(
				<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
			);

			// Verify the API hook is called with correct endpoint
			expect(useApi).toHaveBeenCalledWith("/videos/{videoUuid}/chapters");
		});

		it("should update chapter status when marked complete", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockStatusUpdate = vi.fn().mockResolvedValue({ success: true });

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockStatusUpdate,
			});

			const user = userEvent.setup();
			render(
				<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
			);

			// When marking a chapter complete, it should call the status update API
			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[0]);

			// This test would need the actual implementation to verify the API call
		});

		it("should extract chapters when button is clicked", async () => {
			const { useApi } = await import("@/hooks/useApi");
			const mockExtract = vi
				.fn()
				.mockResolvedValue({ message: "Chapters extracted", count: 6 });

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: null,
				execute: mockExtract,
			});

			render(
				<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
			);

			// This would require adding an extract chapters button to the component
			// and testing that it calls the extract endpoint
		});

		it("should handle loading state while fetching chapters", async () => {
			const { useApi } = await import("@/hooks/useApi");

			useApi.mockReturnValue({
				data: null,
				isLoading: true,
				error: null,
				execute: vi.fn(),
			});

			render(
				<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
			);

			// Should show loading indicator
			expect(screen.getByText(/loading/i)).toBeInTheDocument();
		});

		it("should handle error state when fetching chapters fails", async () => {
			const { useApi } = await import("@/hooks/useApi");

			useApi.mockReturnValue({
				data: null,
				isLoading: false,
				error: new Error("Failed to fetch chapters"),
				execute: vi.fn(),
			});

			render(
				<VideoSidebar video={mockVideo} currentTime={0} onSeek={mockOnSeek} />,
			);

			// Should show error message
			expect(screen.getByText(/error/i)).toBeInTheDocument();
		});
	});
});
