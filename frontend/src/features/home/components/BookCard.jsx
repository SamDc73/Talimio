import { deleteApi } from "@/services/deleteApi";
import {
	calculateBookProgress,
	getBookProgressStats,
} from "@/services/tocProgressService";
import { BookOpen, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { KebabMenu } from "./KebabMenu";
import { TagChip } from "./TagChip";

export function BookCard({ book, onDelete, className = "" }) {
	const [showMenu, setShowMenu] = useState(false);
	const [progress, setProgress] = useState(() => {
		// ALWAYS use saved stats first (they have the correct chapter-based progress)
		const stats = getBookProgressStats(book.id);
		if (stats.totalSections > 0) {
			return stats;
		}

		// If no saved stats but we have table_of_contents, calculate
		if (book.tableOfContents && book.tableOfContents.length > 0) {
			return calculateBookProgress(book.id, book.tableOfContents);
		}

		// Otherwise, no progress yet
		return {
			percentage: 0,
			completedSections: 0,
			totalSections: 0,
			type: "section-based",
		};
	});
	const readingProgress = progress.percentage;

	// Check for updated progress on mount and when book changes
	useEffect(() => {
		// Check if we have updated stats
		const stats = getBookProgressStats(book.id);
		if (stats.totalSections > 0) {
			setProgress(stats);
		}
	}, [book.id]); // Only depend on book.id

	// Listen for localStorage changes to update progress
	useEffect(() => {
		const handleStorageChange = (e) => {
			if (
				e.key === `bookTocProgress_${book.id}` ||
				e.key === `bookProgressStats_${book.id}`
			) {
				// Get updated stats
				const stats = getBookProgressStats(book.id);
				if (stats.totalSections > 0) {
					setProgress(stats);
				} else {
					setProgress(calculateBookProgress(book.id, book.tableOfContents));
				}
			}
		};

		// Listen for storage events from other tabs/windows
		window.addEventListener("storage", handleStorageChange);

		// Custom event for same-tab updates
		const handleProgressUpdate = (e) => {
			if (e.detail.bookId === book.id) {
				const stats = getBookProgressStats(book.id);
				if (stats.totalSections > 0) {
					setProgress(stats);
				}
			}
		};
		window.addEventListener("bookProgressUpdate", handleProgressUpdate);

		return () => {
			window.removeEventListener("storage", handleStorageChange);
			window.removeEventListener("bookProgressUpdate", handleProgressUpdate);
		};
	}, [book.id, book]);

	const handleDelete = async (itemType, itemId) => {
		try {
			await deleteApi.deleteItem(itemType, itemId);
			if (onDelete) {
				onDelete(itemId, itemType);
			}
		} catch (error) {
			console.error("Failed to delete book:", error);
		}
	};

	return (
		<div
			className={`bg-white rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 p-6 relative ${className}`}
			onMouseEnter={() => setShowMenu(true)}
			onMouseLeave={() => setShowMenu(false)}
		>
			{/* Header with badge and menu */}
			<div className="flex justify-between items-start mb-4">
				<div className="flex items-center gap-1.5 text-book">
					<BookOpen className="h-4 w-4" />
					<span className="text-sm">Book</span>
				</div>
			</div>

			<KebabMenu
				showMenu={showMenu}
				onDelete={handleDelete}
				itemType="book"
				itemId={book.id}
				itemTitle={book.title || "Untitled Book"}
			/>

			{/* Title */}
			<h3 className="text-xl font-display font-semibold text-foreground mb-2">
				{book.title || "Untitled Book"}
			</h3>

			{/* Description */}
			<p className="text-muted-foreground text-sm mb-4">
				{book.author || "Unknown Author"}
			</p>

			{/* Tags */}
			<div className="flex flex-wrap gap-2 mb-6">
				{book.tags?.slice(0, 3).map((tag) => (
					<TagChip key={tag} tag={tag} contentType="book" />
				))}
				{book.tags?.length > 3 && (
					<span className="text-xs text-muted-foreground">
						+{book.tags.length - 3}
					</span>
				)}
			</div>

			{/* Progress */}
			<div className="mb-6">
				<div className="text-sm text-muted-foreground mb-2">
					Reading Progress
				</div>
				<div className="flex items-center gap-3">
					<div className="flex-1 bg-gray-100 rounded-full h-2">
						<div
							className="bg-book h-2 rounded-full transition-all duration-300"
							style={{ width: `${readingProgress}%` }}
						/>
					</div>
					<span className="text-sm text-gray-900 font-medium">
						{Math.round(readingProgress)}%
					</span>
				</div>
			</div>

			{/* Footer */}
			<div className="flex justify-between items-center">
				<span className="text-sm text-gray-500">
					{progress.type === "section-based"
						? `${progress.completedSections}/${progress.totalSections} sections`
						: `${progress.completedSections}/${progress.totalSections} pages`}
				</span>
				<Link
					to={`/books/${book.id}`}
					className="flex items-center gap-1 text-book hover:text-book-accent text-sm font-medium transition-colors"
				>
					Read
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</div>
	);
}
