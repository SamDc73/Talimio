import { api } from "./apiClient.js";

/**
 * Fetches content data from the API.
 * @param {boolean} [includeArchived=false] - Whether to include archived content.
 * @returns {Promise<Array>} - A promise that resolves to an array of content items.
 */
export async function fetchContentData(includeArchived = false) {
	try {
		let url = "/content";
		if (includeArchived) {
			url += "?include_archived=true";
		}

		const data = await api.get(url);

		if (import.meta.env.VITE_DEBUG_MODE === "true") {
			console.log("[DEBUG] Raw API response:", data);
		}

		return data.items.map((item) => {
			if (import.meta.env.VITE_DEBUG_MODE === "true") {
				console.log(`🔄 Processing item "${item.title}":`, {
					type: item.type,
					archived: item.archived,
				});
			}

			const mappedItem = {
				id: item.id,
				type: item.type === "youtube" ? "video" : item.type, // Map youtube to video
				title: item.title,
				description: item.description,
				lastAccessedDate: item.lastAccessedDate,
				createdDate: item.createdDate,
				progress: item.progress?.percentage || item.progress || 0, // Extract percentage from ProgressData object
				tags: item.tags || [],
				archived: item.archived || false,
				...(item.type === "youtube" && {
					channel: item.channel, // Use the correct field name from backend
					duration: item.length, // Backend sends 'length' for duration
				}),
				...(item.type === "flashcards" && {
					cardCount: item.cardCount,
					dueCount: item.dueCount,
				}),
				...(item.type === "book" && {
					author: item.author,
					pageCount: item.pageCount,
					currentPage: item.currentPage,
					tocProgress: item.tocProgress || {},
				}),
				...(item.type === "course" && {
					lessonCount: item.lessonCount,
					completedLessons: item.completedLessons,
				}),
			};

			if (import.meta.env.VITE_DEBUG_MODE === "true") {
				console.log(`✅ Mapped item "${mappedItem.title}":`, {
					type: mappedItem.type,
					archived: mappedItem.archived,
					id: mappedItem.id,
				});
			}
			return mappedItem;
		});
	} catch (error) {
		console.error("Error fetching content:", error);
		return [];
	}
}

/**
 * Processes content data to generate filter and sort options.
 * @param {ContentItem[]} data - The content items to process.
 * @returns {{content: ContentItem[], filterOptions: FilterOption[], sortOptions: SortOption[]}} - The processed data with filter and sort options.
 */
export function processContentData(data) {
	const filterOptions = [
		{ id: "all", label: "All Content", icon: "Search" },
		{ id: "course", label: "Courses", icon: "BookOpen" },
		{ id: "video", label: "Videos", icon: "Youtube" },
		{ id: "flashcards", label: "Flashcards", icon: "Layers" },
		{ id: "book", label: "Books", icon: "FileText" },
	];

	const sortOptions = [
		{ id: "last-accessed", label: "Last Opened", icon: "Clock" },
		{ id: "created", label: "Date Created", icon: "CalendarDays" },
		{ id: "progress", label: "Progress", icon: "ArrowUpDown" },
		{ id: "title", label: "Title", icon: "FileText" },
	];

	return {
		content: data,
		filterOptions,
		sortOptions,
	};
}
