import { deleteApi } from "@/services/deleteApi";
import { ChevronRight, Youtube } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { KebabMenu } from "./KebabMenu";
import { TagChip } from "./TagChip";

function formatDuration(seconds) {
	if (!seconds) return "Unknown duration";

	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = seconds % 60;

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function YoutubeCard({ video, onDelete, onArchive, className = "" }) {
	const [showMenu, setShowMenu] = useState(false);

	const handleDelete = async (itemType, itemId) => {
		try {
			await deleteApi.deleteItem(itemType, itemId);
			if (onDelete) {
				onDelete(itemId, itemType);
			}
		} catch (error) {
			console.error("Failed to delete video:", error);
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
				<div className="flex items-center gap-1.5 text-video">
					<Youtube className="h-4 w-4" />
					<span className="text-sm">Video</span>
				</div>
			</div>

			<KebabMenu
				showMenu={showMenu}
				onDelete={handleDelete}
				onArchive={onArchive}
				itemType="youtube"
				itemId={video.uuid || video.id}
				itemTitle={video.title}
				isArchived={video.archived || false}
			/>

			{/* Title */}
			<h3 className="text-xl font-display font-semibold text-foreground mb-2">
				{video.title}
			</h3>

			{/* Description */}
			<p className="text-muted-foreground text-sm mb-4">
				{video.channelName || video.channel} • {formatDuration(video.duration)}
			</p>

			{/* Tags */}
			<div className="flex flex-wrap gap-2 mb-6">
				{video.tags?.slice(0, 3).map((tag) => (
					<TagChip key={tag} tag={tag} contentType="video" />
				))}
				{video.tags?.length > 3 && (
					<span className="text-xs text-muted-foreground">
						+{video.tags.length - 3}
					</span>
				)}
			</div>

			{/* Progress */}
			<div className="mb-6">
				<div className="text-sm text-muted-foreground mb-2">Progress</div>
				<div className="flex items-center gap-3">
					<div className="flex-1 bg-muted rounded-full h-2">
						<div
							className="bg-video h-2 rounded-full transition-all duration-300"
							style={{
								width: `${video.progress || video.completionPercentage || 0}%`,
							}}
						/>
					</div>
					<span className="text-sm text-foreground font-medium">
						{Math.round(video.progress || video.completionPercentage || 0)}%
					</span>
				</div>
			</div>

			{/* Footer */}
			<div className="flex justify-between items-center">
				<span className="text-sm text-muted-foreground">YouTube</span>
				<Link
					to={`/videos/${video.uuid || video.id}`}
					className="flex items-center gap-1 text-video hover:text-video-accent text-sm font-medium transition-colors"
				>
					Watch
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</div>
	);
}
