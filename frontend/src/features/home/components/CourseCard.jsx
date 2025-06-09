import { deleteApi } from "@/services/deleteApi";
import { ChevronRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { KebabMenu } from "./KebabMenu";

export function CourseCard({ course, onDelete }) {
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
			className="bg-white rounded-2xl shadow-sm hover:shadow-md transition-all p-6 relative"
			onMouseEnter={() => setShowMenu(true)}
			onMouseLeave={() => setShowMenu(false)}
		>
			{/* Header with badge and menu */}
			<div className="flex justify-between items-start mb-4">
				<div className="bg-teal-50 text-teal-600 text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1">
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
			<h3 className="text-xl font-semibold text-gray-900 mb-2">
				{course.title}
			</h3>

			{/* Description */}
			<p className="text-gray-600 text-sm mb-4">{course.description}</p>

			{/* Tags */}
			<div className="flex flex-wrap gap-2 mb-6">
				{course.tags?.slice(0, 3).map((tag) => (
					<span
						key={tag}
						className="inline-flex items-center px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 text-xs"
					>
						{tag}
					</span>
				))}
				{course.tags?.length > 3 && (
					<span className="text-xs text-gray-500">
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
							className="bg-teal-500 h-2 rounded-full transition-all duration-300"
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
					className="flex items-center gap-1 text-teal-600 hover:text-teal-700 text-sm font-medium"
				>
					Resume
					<ChevronRight className="h-4 w-4" />
				</Link>
			</div>
		</div>
	);
}
