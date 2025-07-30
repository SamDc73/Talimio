import {
	ArrowUpDown,
	BookOpen,
	CalendarDays,
	Clock,
	FileText,
	Layers,
	Search,
	Youtube,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { processContentData } from "@/lib/api";
import { api } from "@/lib/apiClient";
export function useContentData(filters, pinning) {
	const [contentItems, setContentItems] = useState([]);
	const [filterOptions, setFilterOptions] = useState([]);
	const [sortOptions, setSortOptions] = useState([]);
	const [isLoading, setIsLoading] = useState(true);
	const { toast } = useToast();

	// Load content data function - memoized with useCallback to prevent recreating on every render
	const loadContentData = useCallback(async () => {
		setIsLoading(true);
		try {
			// Include archived content if we're showing archived or all content
			const includeArchived =
				filters.archiveFilter === "archived" || filters.archiveFilter === "all";
			// Loading content data based on archive filter

			// Fetch data using the correct cookie-based API client
			const response = await api.get(
				includeArchived ? "/content?include_archived=true" : "/content",
			);

			// Transform the raw API response to match the expected format
			const data = (response.items || []).map((item) => {
				const mappedItem = {
					id: item.id,
					type: item.type === "youtube" ? "video" : item.type, // Map youtube to video
					title: item.title,
					description: item.description,
					lastAccessedDate: item.lastAccessedDate,
					createdDate: item.createdDate,
					progress: item.progress?.percentage || item.progress || 0, // Extract percentage from progress object
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
				return mappedItem;
			});

			// Process the API data

			const {
				content,
				filterOptions: options,
				sortOptions: sortOpts,
			} = processContentData(data);

			// Content processed successfully

			// Transform content with additional fields - tags come from backend
			const transformedContent = content.map((item) => ({
				...item,
				// Tags are already included from backend response
				// Add mock due dates and states for demonstration
				dueDate:
					Math.random() > 0.7
						? new Date(
								Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
							).toISOString()
						: null,
				isPaused: Math.random() > 0.9,
				// For flashcards, map the existing fields
				totalCards: item.cardCount,
				due: item.dueCount || Math.floor(Math.random() * 10),
				overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
			}));

			// Set content items without fetching progress (React Query will handle it)
			setContentItems(transformedContent);

			// Map the filter options with their icons
			setFilterOptions(
				options.map((option) => {
					const getIcon = () => {
						switch (option.icon) {
							case "Search":
								return <Search className="h-4 w-4 mr-2" />;
							case "BookOpen":
								return <BookOpen className="h-4 w-4 mr-2" />;
							case "FileText":
								return <FileText className="h-4 w-4 mr-2" />;
							case "Youtube":
								return <Youtube className="h-4 w-4 mr-2" />;
							case "Layers":
								return <Layers className="h-4 w-4 mr-2" />;
							default:
								return <Search className="h-4 w-4 mr-2" />;
						}
					};

					return {
						...option,
						icon: getIcon(),
					};
				}),
			);

			// Map the sort options with their icons
			setSortOptions(
				sortOpts.map((option) => {
					const getIcon = () => {
						switch (option.icon) {
							case "Clock":
								return <Clock className="h-4 w-4 mr-2" />;
							case "CalendarDays":
								return <CalendarDays className="h-4 w-4 mr-2" />;
							case "ArrowUpDown":
								return <ArrowUpDown className="h-4 w-4 mr-2" />;
							case "FileText":
								return <FileText className="h-4 w-4 mr-2" />;
							default:
								return <Clock className="h-4 w-4 mr-2" />;
						}
					};

					return {
						...option,
						icon: getIcon(),
					};
				}),
			);

			// Initialize pins state
			pinning.initializePins(transformedContent);
		} catch (error) {
			console.error("Error loading content data:", error);
			toast({
				title: "Error",
				description: "Failed to load content. Please refresh the page.",
				variant: "destructive",
			});
		} finally {
			setIsLoading(false);
		}
	}, [filters.archiveFilter, toast, pinning.initializePins]);

	// Fetch content data on component mount and when archive filter changes
	useEffect(() => {
		loadContentData();
	}, [loadContentData]);

	// Removed event listeners that caused race condition
	// These events are now handled by useContentProgressSync hook

	return {
		contentItems,
		setContentItems,
		filterOptions,
		setFilterOptions,
		sortOptions,
		setSortOptions,
		isLoading,
		loadContentData,
	};
}
