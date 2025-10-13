import { Loader2, Tag as TagIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import useTagStore from "../../../stores/useTagStore"

import { TagList } from "./Tag"
import TagInput from "./TagInput"

/**
 * Modal for editing tags on content items
 */
function TagEditModal({ open, onOpenChange, contentType, contentId, contentTitle = "", onTagsUpdated }) {
	const [currentTags, setCurrentTags] = useState([])
	const [isLoading, setIsLoading] = useState(false)
	const [isSaving, setIsSaving] = useState(false)

	const { fetchContentTags, updateContentTags, fetchUserTags, getContentTagObjects } = useTagStore()

	const loadContentTags = async () => {
		setIsLoading(true)
		try {
			const tags = await fetchContentTags(contentType, contentId)
			setCurrentTags(tags)
		} catch (_error) {
			console.log("Error")
		} finally {
			setIsLoading(false)
		}
	}

	// Load content tags when modal opens
	useEffect(() => {
		if (open && contentType && contentId) {
			loadContentTags()
			// Also ensure we have user tags loaded
			fetchUserTags()
		}
	}, [open, contentType, contentId, fetchUserTags, loadContentTags])

	const handleSave = async () => {
		setIsSaving(true)
		try {
			const tagNames = currentTags.map((tag) => tag.name)
			await updateContentTags(contentType, contentId, tagNames)

			console.log("Action completed")

			// Notify parent component that tags were updated
			if (onTagsUpdated) {
				onTagsUpdated(contentId, contentType, tagNames)
			}

			onOpenChange(false)
		} catch (_error) {
			console.log("Error")
		} finally {
			setIsSaving(false)
		}
	}

	const handleCancel = () => {
		// Reset to original tags
		const originalTags = getContentTagObjects(contentType, contentId)
		setCurrentTags(originalTags)
		onOpenChange(false)
	}

	if (!contentType || !contentId) {
		return null
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						<TagIcon className="h-5 w-5" />
						Edit Tags
					</DialogTitle>
					{contentTitle && <p className="text-sm text-gray-600 mt-1">for "{contentTitle}"</p>}
				</DialogHeader>

				<div className="space-y-4 py-4">
					{isLoading ? (
						<div className="flex items-center justify-center py-8">
							<Loader2 className="h-6 w-6 animate-spin" />
							<span className="ml-2 text-sm text-gray-600">Loading tags...</span>
						</div>
					) : (
						<>
							{/* Current tags display */}
							{currentTags.length > 0 ? (
								<div>
									<div className="text-sm font-medium text-gray-700 mb-2 block">Current Tags</div>
									<TagList tags={currentTags} variant="default" size="medium" />
								</div>
							) : (
								<div className="text-center py-4 text-gray-500">
									<div className="text-sm">This item has no tags yet</div>
									<div className="text-xs mt-1">Start typing below to add tags</div>
								</div>
							)}

							{/* Tag input */}
							<div>
								<div className="text-sm font-medium text-gray-700 mb-2 block">
									{currentTags.length > 0 ? "Add/Remove Tags" : "Add Tags"}
								</div>
								<TagInput
									selectedTags={currentTags}
									onTagsChange={setCurrentTags}
									placeholder="Search or create tags..."
									maxTags={20}
									allowCreate={true}
								/>
							</div>

							{/* Helper text */}
							<div className="text-xs text-gray-500 bg-gray-50 p-3 rounded">
								<p>• Type to search existing tags or create new ones</p>
								<p>• Press Enter to add a tag</p>
								<p>• Click the X on a tag to remove it</p>
							</div>
						</>
					)}
				</div>

				{/* Actions */}
				<div className="flex justify-end gap-2 pt-4 border-t">
					<Button type="button" variant="outline" onClick={handleCancel} disabled={isSaving}>
						Cancel
					</Button>
					<Button type="button" onClick={handleSave} disabled={isSaving || isLoading}>
						{isSaving ? (
							<>
								<Loader2 className="h-4 w-4 animate-spin mr-2" />
								Saving...
							</>
						) : (
							"Save Tags"
						)}
					</Button>
				</div>
			</DialogContent>
		</Dialog>
	)
}

export default TagEditModal
