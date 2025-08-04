import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useProgress } from "@/hooks/useProgress";

/**
 * Progress bar with optimistic updates and sync indication
 */
export function ProgressBar({
	contentId,
	initialProgress = 0,
	className = "",
}) {
	const [optimisticProgress, setOptimisticProgress] = useState(initialProgress);
	const { data: progressMap } = useProgress([contentId]);

	// Use server progress when available, optimistic otherwise
	const serverProgress = progressMap?.[contentId];
	const displayProgress = serverProgress ?? optimisticProgress;
	const isSyncing = optimisticProgress !== displayProgress;

	// Update optimistic progress when server progress changes
	useEffect(() => {
		if (serverProgress !== undefined) {
			setOptimisticProgress(serverProgress);
		}
	}, [serverProgress]);

	return (
		<div className={`relative w-full ${className}`}>
			<div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
				<div
					className="bg-teal-500 h-2.5 rounded-full transition-all duration-300 ease-out"
					style={{ width: `${displayProgress}%` }}
				/>
			</div>

			{/* Sync indicator */}
			{isSyncing && (
				<div className="absolute -right-6 top-1/2 -translate-y-1/2">
					<Loader2 className="h-4 w-4 animate-spin text-gray-400" />
				</div>
			)}

			{/* Progress percentage */}
			<span className="text-sm text-gray-600 mt-1">
				{Math.round(displayProgress)}%
			</span>
		</div>
	);
}

/**
 * Progress bar for use in content cards
 */
export function ContentProgressBar({ progress, loading = false }) {
	if (loading) {
		return (
			<div className="w-full bg-gray-200 rounded-full h-2.5 animate-pulse">
				<div className="bg-gray-300 h-2.5 rounded-full w-0" />
			</div>
		);
	}

	return (
		<div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
			<div
				className="bg-teal-500 h-2.5 rounded-full transition-all duration-300 ease-out"
				style={{ width: `${progress}%` }}
			/>
		</div>
	);
}
