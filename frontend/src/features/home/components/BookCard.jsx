import { BookOpen, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { deleteApi } from "@/services/deleteApi";
import { KebabMenu } from "./KebabMenu";
import { TagChip } from "./TagChip";

export function BookCard({ book, onDelete, onArchive, className = "" }) {
	const [showMenu, setShowMenu] = useState(false);
	// Use API-provided progress, just like CourseCard does
	const readingProgress = book.progress || 0;

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
		<button
			type="button"
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
				onArchive={onArchive}
				itemType="book"
				itemId={book.id}
				itemTitle={book.title || "Untitled Book"}
				isArchived={book.archived || false}
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
					<div className="flex-1 bg-muted rounded-full h-2">
						<div
							className="bg-book h-2 rounded-full transition-all duration-300"
							style={{ width: `${readingProgress}%` }}
						/>
					</div>
					<span className="text-sm text-foreground font-medium">
						{Math.round(readingProgress)}%
					</span>
				</div>
			</div>

			{/* Footer */}
			<div className="flex justify-between items-center">
				<span className="text-sm text-muted-foreground">
					{book.totalPages || 0} pages
				</span>
				<Link
					to={`/books/${book.id}`}
					className="flex items-center gap-1 text-book hover:text-book-accent text-sm font-medium transition-colors"
				>
					Read
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</button>
	);
}
