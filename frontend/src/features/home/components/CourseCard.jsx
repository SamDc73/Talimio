import { deleteApi } from "@/services/deleteApi";
import { ChevronRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { KebabMenu } from "./KebabMenu";
import { TagChip } from "./TagChip";

export function CourseCard({ course, onDelete, className = "" }) {
	const [showMenu, setShowMenu] = useState(false);

	const handleDelete = async (itemType, itemId) => {
		try {
			await deleteApi.deleteItem(itemType, itemId);
			if (onDelete) {
				onDelete(itemId, itemType);
			}
		} catch (error) {
			console.error("Failed to delete course:", error);
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
				<div className="bg-course/10 text-course-text text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1">
					<Sparkles className="h-3 w-3" />
					<span>Course</span>
				</div>
			</div>

			<KebabMenu
				showMenu={showMenu}
				onDelete={handleDelete}
				itemType="roadmap"
				itemId={course.id}
				itemTitle={course.title}
			/>

			{/* Title */}
			<h3 className="text-xl font-display font-semibold text-foreground mb-2">
				{course.title}
			</h3>

			{/* Description */}
			<p className="text-muted-foreground text-sm mb-4">{course.description}</p>

			{/* Tags */}
			<div className="flex flex-wrap gap-2 mb-6">
				{course.tags?.slice(0, 3).map((tag) => (
					<TagChip key={tag} tag={tag} contentType="course" />
				))}
				{course.tags?.length > 3 && (
					<span className="text-xs text-muted-foreground">
						+{course.tags.length - 3}
					</span>
				)}
			</div>

			{/* Progress */}
			<div className="mb-6">
				<div className="text-sm text-gray-600 mb-2">Progress</div>
				<div className="flex items-center gap-3">
					<div className="flex-1 bg-gray-100 rounded-full h-2">
						<div
							className="bg-course h-2 rounded-full transition-all duration-300"
							style={{ width: `${course.progress || 0}%` }}
						/>
					</div>
					<span className="text-sm text-gray-900 font-medium">
						{course.progress || 0}%
					</span>
				</div>
			</div>

			{/* Footer */}
			<div className="flex justify-between items-center">
				<span className="text-sm text-gray-500">
					{course.modules || 0} modules
				</span>
				<Link
					to={`/courses/${course.id}`}
					className="flex items-center gap-1 text-course hover:text-course-accent text-sm font-medium transition-colors"
				>
					Resume
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</div>
	);
}
