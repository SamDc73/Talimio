import useAppStore from "../stores/useAppStore";

const API_BASE = "/api/v1";
const REQUEST_TIMEOUT = 10000; // 10 seconds

/**
 * @typedef {Object} ContentItem
 * @property {string} id - The unique identifier for the content item
 * @property {"youtube" | "flashcards" | "book" | "roadmap" | "course"} type - The type of content
 * @property {string} title - The title of the content
 * @property {string} description - The description of the content
 * @property {string} lastAccessedDate - The last accessed date of the content
 * @property {string} createdDate - The created date of the content
 * @property {number} progress - The progress of the content (0-100)
 * @property {string[]} tags - An array of tags associated with the content
 * @property {boolean} [archived] - Whether the content is archived
 * @property {string} [channelName] - YouTube specific: channel name
 * @property {string} [channel_name] - YouTube specific: channel name (alternative)
 * @property {number} [duration] - YouTube specific: duration in seconds
 * @property {number} [cardCount] - Flashcards specific: number of cards
 * @property {number} [dueCount] - Flashcards specific: number of due cards
 * @property {string} [author] - Book specific: author name
 * @property {number} [pageCount] - Book specific: total page count
 * @property {number} [pages] - Book specific: total page count (alternative)
 * @property {number} [currentPage] - Book specific: current page number
 * @property {number} [nodeCount] - Roadmap specific: total node count
 * @property {number} [completedNodes] - Roadmap specific: completed node count
 * @property {number} [modules] - Course specific: number of modules
 */

/**
 * @typedef {Object} FilterOption
 * @property {string} id
 * @property {string} label
 * @property {"Search" | "Youtube" | "Layers" | "BookOpen" | "FileText"} icon
 */

/**
 * @typedef {Object} SortOption
 * @property {string} id
 * @property {string} label
 * @property {"Clock" | "CalendarDays" | "ArrowUpDown" | "FileText"} icon
 */

async function request(url, options = {}) {
	const { token } = useAppStore.getState();
	const headers = {
		"Content-Type": "application/json",
		...options.headers,
	};

	if (token) {
		headers.Authorization = `Bearer ${token}`;
	}

	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

	try {
		const response = await fetch(url, {
			...options,
			headers,
			credentials:
				import.meta.env.VITE_ENABLE_AUTH === "false" ? "omit" : "include",
			signal: controller.signal,
		});
		clearTimeout(timeout);

		if (!response.ok) {
			const errorData = await response
				.json()
				.catch(() => ({ message: response.statusText }));
			const error = new Error(errorData.message || "API request failed");
			error.status = response.status;
			error.data = errorData;
			throw error;
		}

		if (response.status === 204) {
			return null;
		}

		return response.json();
	} catch (error) {
		clearTimeout(timeout);
		if (error.name === "AbortError") {
			throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`);
		}
		throw error;
	}
}

export const api = {
	get: (url, options) => request(url, { ...options, method: "GET" }),
	post: (url, body, options) =>
		request(url, { ...options, method: "POST", body: JSON.stringify(body) }),
	put: (url, body, options) =>
		request(url, { ...options, method: "PUT", body: JSON.stringify(body) }),
	patch: (url, body, options) =>
		request(url, { ...options, method: "PATCH", body: JSON.stringify(body) }),
	delete: (url, options) => request(url, { ...options, method: "DELETE" }),
};

/**
 * Fetches content data from the API.
 * @param {boolean} [includeArchived=false] - Whether to include archived content.
 * @returns {Promise<ContentItem[]>} - A promise that resolves to an array of ContentItem objects.
 */
export async function fetchContentData(includeArchived = false) {
	try {
		let url = `${API_BASE}/content`;
		if (includeArchived) {
			url += "?include_archived=true";
		}

		const data = await api.get(url);

		if (import.meta.env.VITE_DEBUG_MODE === "true") {
			console.log("[DEBUG] Raw API response:", data);
		}

		return data.items.map((item) => {
			console.log(`🔄 Processing item "${item.title}":`, {
				type: item.type,
				archived: item.archived,
				willMapTo: item.archived || false,
			});

			const mappedItem = {
				id: item.id,
				type: item.type,
				title: item.title,
				description: item.description,
				lastAccessedDate: item.lastAccessedDate,
				createdDate: item.createdDate,
				progress: item.progress || 0,
				tags: item.tags || [],
				archived: item.archived || false,
				...(item.type === "youtube" && {
					channelName: item.channelName || item.channel_name,
					channel_name: item.channelName || item.channel_name,
					duration: item.duration,
				}),
				...(item.type === "flashcards" && {
					cardCount: item.cardCount,
					dueCount: item.dueCount,
				}),
				...(item.type === "book" && {
					author: item.author,
					pageCount: item.pageCount || item.page_count,
					pages: item.pageCount || item.page_count,
					currentPage: item.currentPage || item.current_page,
					tocProgress: item.tocProgress || {},
				}),
				...(item.type === "roadmap" && {
					nodeCount: item.nodeCount,
					completedNodes: item.completedNodes,
				}),
				...(item.type === "course" && {
					modules: item.modules,
				}),
			};

			console.log(`✅ Mapped item "${mappedItem.title}":`, {
				type: mappedItem.type,
				archived: mappedItem.archived,
				id: mappedItem.id,
			});
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
		{ id: "youtube", label: "Videos", icon: "Youtube" },
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
