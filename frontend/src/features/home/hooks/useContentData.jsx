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
import { fetchContentData, processContentData } from "@/lib/api";
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
			console.log(
				`🔄 Loading content data with archiveFilter: ${filters.archiveFilter}, includeArchived: ${includeArchived}`,
			);

			const data = await fetchContentData(includeArchived);
			console.log("📦 Raw API data received:", data);

			const {
				content,
				filterOptions: options,
				sortOptions: sortOpts,
			} = processContentData(data);

			console.log("⚙️ Processed content:", content);
			console.log("📊 Archive status breakdown:", {
				total: content.length,
				archived: content.filter((item) => item.archived).length,
				active: content.filter((item) => !item.archived).length,
			});

			// Batch process tags to avoid too many concurrent requests
			// Process in chunks of 5 to prevent overwhelming the browser
			const BATCH_SIZE = 5;
			const transformedContent = [];

			for (let i = 0; i < content.length; i += BATCH_SIZE) {
				const batch = content.slice(i, i + BATCH_SIZE);
				const batchResults = await Promise.all(
					batch.map(async (item) => {
						// Load tags from tag associations for each item
						let tags = [];
						try {
							const contentType =
								item.type === "youtube"
									? "video"
									: item.type === "flashcards"
										? "flashcard"
										: item.type === "course"
											? "roadmap" // Map course to roadmap for tags API
											: item.type;
							const contentId = item.id || item.uuid;
							if (contentId && contentType) {
								const response = await fetch(
									`/api/tags/${contentType}/${contentId}/tags`,
								);
								if (response.ok) {
									const tagData = await response.json();
									tags = tagData.map((tag) => tag.name);
								}
							}
						} catch (error) {
							console.log(`Could not load tags for ${item.title}:`, error);
						}

						return {
							...item,
							tags, // Use tags from tag associations instead of book endpoint
							// Add mock due dates and states for demonstration
							dueDate:
								Math.random() > 0.7
									? new Date(
											Date.now() +
												(Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
										).toISOString()
									: null,
							isPaused: Math.random() > 0.9,
							// For flashcards, map the existing fields
							totalCards: item.cardCount,
							due: item.dueCount || Math.floor(Math.random() * 10),
							overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
						};
					}),
				);
				transformedContent.push(...batchResults);
			}

			const courseItems = transformedContent.filter(
				(item) => item.type === "course",
			);
			if (courseItems.length > 0) {
				// Use Promise.allSettled to handle individual API failures gracefully
				const courseProgressPromises = courseItems.map((course) =>
					api.get(`/courses/${course.id}/progress`).catch((error) => {
						console.error(
							`Failed to fetch progress for course ${course.id}:`,
							error,
						);
						// Return a default progress object for failed requests
						return {
							completion_percentage: 0,
							total_lessons: 0,
							completed_lessons: 0,
							error: true,
						};
					}),
				);
				const courseProgresses = await Promise.all(courseProgressPromises);

				console.log("🎯 Course progress API responses:", courseProgresses);

				const coursesWithProgress = courseItems.map((course, index) => ({
					...course,
					progress: courseProgresses[index].completion_percentage || 0, // Fixed: Remove .data since apiClient returns direct JSON
				}));

				const contentWithProgress = transformedContent.map((item) => {
					if (item.type === "course") {
						const courseWithProgress = coursesWithProgress.find(
							(c) => c.id === item.id,
						);
						return courseWithProgress || item;
					}
					return item;
				});
				setContentItems(contentWithProgress);
			} else {
				setContentItems(transformedContent);
			}

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
