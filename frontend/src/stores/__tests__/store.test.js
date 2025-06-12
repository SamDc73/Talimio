/**
 * Tests for the Zustand store
 */
import useAppStore from "../useAppStore";

describe("useAppStore", () => {
	beforeEach(() => {
		// Reset store before each test
		useAppStore.getState().clearAllData();
	});

	describe("Books Slice", () => {
		test("updateBookProgress should update book progress", () => {
			const bookId = "test-book-123";
			const progress = {
				currentPage: 50,
				totalPages: 200,
				zoomLevel: 1.5,
			};

			useAppStore.getState().updateBookProgress(bookId, progress);

			const storedProgress = useAppStore.getState().getBookProgress(bookId);
			expect(storedProgress.currentPage).toBe(50);
			expect(storedProgress.totalPages).toBe(200);
			expect(storedProgress.zoomLevel).toBe(1.5);
			expect(storedProgress.lastUpdated).toBeDefined();
		});

		test("updateBookChapterStatus should update chapter completion", () => {
			const bookId = "test-book-123";
			const chapterId = "chapter-1";

			useAppStore.getState().updateBookChapterStatus(bookId, chapterId, true);

			const chapterStatus =
				useAppStore.getState().books.chapterCompletion[bookId];
			expect(chapterStatus[chapterId]).toBe(true);
		});

		test("getBookProgress should return defaults for unknown book", () => {
			const progress = useAppStore.getState().getBookProgress("unknown-book");

			expect(progress).toEqual({
				currentPage: 1,
				totalPages: 0,
				zoomLevel: 1,
				scrollPosition: { x: 0, y: 0 },
			});
		});
	});

	describe("Videos Slice", () => {
		test("updateVideoProgress should update video progress", () => {
			const videoId = "test-video-456";
			const progress = {
				currentTime: 300,
				duration: 600,
				playbackRate: 1.25,
				volume: 0.8,
			};

			useAppStore.getState().updateVideoProgress(videoId, progress);

			const storedProgress = useAppStore.getState().getVideoProgress(videoId);
			expect(storedProgress.currentTime).toBe(300);
			expect(storedProgress.duration).toBe(600);
			expect(storedProgress.playbackRate).toBe(1.25);
			expect(storedProgress.volume).toBe(0.8);
		});
	});

	describe("Preferences Slice", () => {
		test("updatePreference should update individual preferences", () => {
			useAppStore.getState().updatePreference("theme", "dark");
			expect(useAppStore.getState().preferences.theme).toBe("dark");

			useAppStore.getState().updatePreference("autoPlayVideos", false);
			expect(useAppStore.getState().preferences.autoPlayVideos).toBe(false);
		});

		test("toggleTheme should cycle through themes", () => {
			const { toggleTheme, preferences } = useAppStore.getState();

			// Initial state
			expect(preferences.theme).toBe("system");

			// Toggle to light
			toggleTheme();
			expect(useAppStore.getState().preferences.theme).toBe("light");

			// Toggle to dark
			toggleTheme();
			expect(useAppStore.getState().preferences.theme).toBe("dark");

			// Toggle back to system
			toggleTheme();
			expect(useAppStore.getState().preferences.theme).toBe("system");
		});
	});

	describe("UI Slice", () => {
		test("toggleSidebar should toggle sidebar state", () => {
			const initialState = useAppStore.getState().ui.sidebarOpen;

			useAppStore.getState().toggleSidebar();
			expect(useAppStore.getState().ui.sidebarOpen).toBe(!initialState);

			useAppStore.getState().toggleSidebar();
			expect(useAppStore.getState().ui.sidebarOpen).toBe(initialState);
		});

		test("modal management should work correctly", () => {
			const modalData = { bookId: "123", title: "Test Book" };

			useAppStore.getState().setActiveModal("deleteConfirm", modalData);
			expect(useAppStore.getState().ui.activeModal).toBe("deleteConfirm");
			expect(useAppStore.getState().ui.modalData).toEqual(modalData);

			useAppStore.getState().closeModal();
			expect(useAppStore.getState().ui.activeModal).toBeNull();
			expect(useAppStore.getState().ui.modalData).toBeNull();
		});

		test("loading states should be managed correctly", () => {
			useAppStore.getState().setLoading("books", true);
			expect(useAppStore.getState().ui.loading.books).toBe(true);

			useAppStore.getState().setLoading("videos", true);
			expect(useAppStore.getState().ui.loading.videos).toBe(true);

			useAppStore.getState().setLoading("books", false);
			expect(useAppStore.getState().ui.loading.books).toBeUndefined();
			expect(useAppStore.getState().ui.loading.videos).toBe(true);
		});

		test("error management should work correctly", () => {
			useAppStore.getState().addError("Test error message");

			const errors = useAppStore.getState().ui.errors;
			expect(errors).toHaveLength(1);
			expect(errors[0].message).toBe("Test error message");
			expect(errors[0].id).toBeDefined();

			const errorId = errors[0].id;
			useAppStore.getState().removeError(errorId);
			expect(useAppStore.getState().ui.errors).toHaveLength(0);
		});
	});

	describe("Roadmaps Slice", () => {
		test("updateNodeCompletion should update node status", () => {
			const roadmapId = "roadmap-789";
			const nodeId = "node-1";

			useAppStore.getState().updateNodeCompletion(roadmapId, nodeId, true);

			const nodeStatus =
				useAppStore.getState().roadmaps.nodeCompletion[roadmapId];
			expect(nodeStatus[nodeId]).toBe(true);
		});

		test("setActiveRoadmap should update active roadmap", () => {
			const roadmapId = "roadmap-789";

			useAppStore.getState().setActiveRoadmap(roadmapId);
			expect(useAppStore.getState().roadmaps.activeRoadmapId).toBe(roadmapId);
		});
	});

	describe("Global Actions", () => {
		test("clearAllData should reset all slices", () => {
			// Add some data
			useAppStore.getState().updateBookProgress("book-1", { currentPage: 10 });
			useAppStore
				.getState()
				.updateVideoProgress("video-1", { currentTime: 100 });
			useAppStore.getState().addError("Test error");

			// Clear all data
			useAppStore.getState().clearAllData();

			// Verify everything is cleared
			expect(useAppStore.getState().books.progress).toEqual({});
			expect(useAppStore.getState().videos.progress).toEqual({});
			expect(useAppStore.getState().ui.errors).toEqual([]);
		});
	});
});

// Run a quick smoke test
console.log("🧪 Running store smoke test...");

const state = useAppStore.getState();

// Test book progress
state.updateBookProgress("test-book", { currentPage: 10, totalPages: 100 });
console.log("✅ Book progress:", state.getBookProgress("test-book"));

// Test video progress
state.updateVideoProgress("test-video", { currentTime: 60, duration: 300 });
console.log("✅ Video progress:", state.getVideoProgress("test-video"));

// Test preferences
state.toggleTheme();
console.log("✅ Theme:", state.preferences.theme);

// Test UI
state.toggleSidebar();
console.log("✅ Sidebar open:", state.ui.sidebarOpen);

console.log("✅ Store smoke test passed!");
