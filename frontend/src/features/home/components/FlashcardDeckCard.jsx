import { ChevronRight, Layers } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { deleteApi } from "@/services/deleteApi";
import { KebabMenu } from "./KebabMenu";
import { TagChip } from "./TagChip";

export function FlashcardDeckCard({
	deck,
	onDelete,
	onArchive,
	className = "",
}) {
	const [showMenu, setShowMenu] = useState(false);
	// Calculate progress percentage based on mastery
	const progressPercentage = (deck.masteryLevel / 5) * 100;

	const handleDelete = async (itemType, itemId) => {
		try {
			await deleteApi.deleteItem(itemType, itemId);
			if (onDelete) {
				onDelete(itemId, itemType);
			}
		} catch (error) {
			console.error("Failed to delete flashcard deck:", error);
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
				<div className="flex items-center gap-1.5 text-flashcard">
					<Layers className="h-4 w-4" />
					<span className="text-sm">Flashcards</span>
				</div>
			</div>

			<KebabMenu
				showMenu={showMenu}
				onDelete={handleDelete}
				onArchive={onArchive}
				itemType="flashcards"
				itemId={deck.id}
				itemTitle={deck.title}
				isArchived={deck.archived || false}
			/>

			{/* Title */}
			<h3 className="text-xl font-display font-semibold text-foreground mb-2">
				{deck.title}
			</h3>

			{/* Description */}
			<p className="text-muted-foreground text-sm mb-4">{deck.description}</p>

			{/* Tags */}
			<div className="flex flex-wrap gap-2 mb-6">
				{deck.tags?.slice(0, 3).map((tag) => (
					<TagChip key={tag} tag={tag} contentType="flashcard" />
				))}
				{deck.tags?.length > 3 && (
					<span className="text-xs text-muted-foreground">
						+{deck.tags.length - 3}
					</span>
				)}
			</div>

			{/* Progress */}
			<div className="mb-6">
				<div className="text-sm text-muted-foreground mb-2">Mastery Level</div>
				<div className="flex items-center gap-3">
					<div className="flex-1 bg-muted rounded-full h-2">
						<div
							className="bg-flashcard h-2 rounded-full transition-all duration-300"
							style={{ width: `${progressPercentage}%` }}
						/>
					</div>
					<span className="text-sm text-foreground font-medium">
						Level {deck.masteryLevel}
					</span>
				</div>
			</div>

			{/* Footer */}
			<div className="flex justify-between items-center">
				<span className="text-sm text-muted-foreground">
					{deck.totalCards} cards • {deck.due} due
				</span>
				<Link
					to={`/flashcards/${deck.id}`}
					className="flex items-center gap-1 text-flashcard hover:text-flashcard-accent text-sm font-medium transition-colors"
				>
					Review
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</div>
	);
}
