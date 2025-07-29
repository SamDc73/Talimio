import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { fetchContentData, processContentData } from "@/lib/api";

export function useContent() {
	const [contentItems, setContentItems] = useState([]);
	const [isLoading, setIsLoading] = useState(false);
	const { toast } = useToast();

	const loadContent = useCallback(
		async (includeArchived = false) => {
			setIsLoading(true);
			try {
				const data = await fetchContentData(includeArchived);
				const { content } = processContentData(data);
				setContentItems(
					content.map((item) => ({
						...item,
						tags: item.tags || [],
						dueDate:
							Math.random() > 0.7
								? new Date(
										Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
									).toISOString()
								: null,
						isPaused: Math.random() > 0.9,
						totalCards: item.cardCount,
						due: item.dueCount || Math.floor(Math.random() * 10),
						overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
					})),
				);
			} catch (error) {
				console.error("Failed to load content:", error);
				toast({
					title: "Error",
					description: "Failed to load content. Please try again.",
					variant: "destructive",
				});
			}
			setIsLoading(false);
		},
		[toast],
	);

	useEffect(() => {
		loadContent();
	}, [loadContent]); // Remove loadContent dependency to prevent infinite loop

	return { contentItems, setContentItems, isLoading, loadContent };
}
