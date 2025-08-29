import { Plus, Search, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import useTagStore from "../../../stores/useTagStore"

import Tag, { TagList } from "./Tag"

/**
 * TagInput component with autocomplete and tag creation
 */
function TagInput({
	selectedTags = [],
	onTagsChange,
	placeholder = "Add tags...",
	maxTags = 10,
	allowCreate = true,
	className = "",
	disabled = false,
}) {
	const [inputValue, setInputValue] = useState("")
	const [isOpen, setIsOpen] = useState(false)
	const [highlightedIndex, setHighlightedIndex] = useState(-1)
	const inputRef = useRef(null)
	const dropdownRef = useRef(null)

	// Tag store
	const { getFilteredTags, getRecentTags, createTag, addToRecentTags, setFilter, clearFilters, loading } = useTagStore()

	// Get filtered suggestions
	const [suggestions, setSuggestions] = useState([])

	useEffect(() => {
		if (inputValue.trim()) {
			setFilter("searchQuery", inputValue)
			const filtered = getFilteredTags()
			// Filter out already selected tags
			const available = filtered.filter((tag) => !selectedTags.some((selected) => selected.id === tag.id))
			setSuggestions(available.slice(0, 8))
		} else {
			clearFilters()
			const recent = getRecentTags()
			// Filter out already selected tags
			const available = recent.filter((tag) => !selectedTags.some((selected) => selected.id === tag.id))
			setSuggestions(available)
		}
	}, [inputValue, selectedTags, getFilteredTags, getRecentTags, setFilter, clearFilters])

	// Handle input change
	const handleInputChange = (e) => {
		setInputValue(e.target.value)
		setHighlightedIndex(-1)
		if (!isOpen) setIsOpen(true)
	}

	// Handle input focus
	const handleInputFocus = () => {
		setIsOpen(true)
	}

	// Handle input blur
	const handleInputBlur = (_e) => {
		// Delay closing to allow click on suggestions
		setTimeout(() => {
			if (!dropdownRef.current?.contains(document.activeElement)) {
				setIsOpen(false)
			}
		}, 150)
	}

	// Handle keyboard navigation
	const handleKeyDown = (e) => {
		if (!isOpen) return

		switch (e.key) {
			case "ArrowDown":
				e.preventDefault()
				setHighlightedIndex((prev) =>
					prev < suggestions.length - 1 + (allowCreate && inputValue.trim() ? 1 : 0) ? prev + 1 : prev
				)
				break
			case "ArrowUp":
				e.preventDefault()
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : prev))
				break
			case "Enter":
				e.preventDefault()
				if (highlightedIndex >= 0) {
					if (highlightedIndex < suggestions.length) {
						// Select existing tag
						handleTagSelect(suggestions[highlightedIndex])
					} else if (allowCreate && inputValue.trim()) {
						// Create new tag
						handleCreateTag()
					}
				} else if (inputValue.trim()) {
					// Try to create new tag or find exact match
					const exactMatch = suggestions.find((tag) => tag.name.toLowerCase() === inputValue.toLowerCase())
					if (exactMatch) {
						handleTagSelect(exactMatch)
					} else if (allowCreate) {
						handleCreateTag()
					}
				}
				break
			case "Escape":
				setIsOpen(false)
				setInputValue("")
				setHighlightedIndex(-1)
				inputRef.current?.blur()
				break
		}
	}

	// Handle tag selection
	const handleTagSelect = (tag) => {
		if (selectedTags.length >= maxTags) return

		const newTags = [...selectedTags, tag]
		onTagsChange(newTags)
		addToRecentTags(tag.id)
		setInputValue("")
		setIsOpen(false)
		setHighlightedIndex(-1)
		inputRef.current?.focus()
	}

	// Handle tag creation
	const handleCreateTag = async () => {
		if (!inputValue.trim() || selectedTags.length >= maxTags) return

		try {
			const newTag = await createTag({
				name: inputValue.trim(),
				category: null,
				color: null,
			})

			const newTags = [...selectedTags, newTag]
			onTagsChange(newTags)
			setInputValue("")
			setIsOpen(false)
			setHighlightedIndex(-1)
			inputRef.current?.focus()
		} catch (_error) {
			// You might want to show a toast notification here
		}
	}

	// Handle tag removal
	const handleTagRemove = (tagToRemove) => {
		const newTags = selectedTags.filter((tag) => tag.id !== tagToRemove.id)
		onTagsChange(newTags)
	}

	// Check if input value would create a duplicate
	const wouldCreateDuplicate =
		inputValue.trim() && suggestions.some((tag) => tag.name.toLowerCase() === inputValue.toLowerCase())

	return (
		<div className={`relative ${className}`}>
			{/* Selected tags */}
			{selectedTags.length > 0 && (
				<div className="mb-2">
					<TagList tags={selectedTags} variant="removable" size="medium" onTagRemove={handleTagRemove} />
				</div>
			)}

			{/* Input field */}
			<div className="relative">
				<div className="flex items-center border border-gray-300 rounded-lg bg-white focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500">
					<Search className="ml-3 h-4 w-4 text-gray-400" />
					<input
						ref={inputRef}
						type="text"
						value={inputValue}
						onChange={handleInputChange}
						onFocus={handleInputFocus}
						onBlur={handleInputBlur}
						onKeyDown={handleKeyDown}
						placeholder={selectedTags.length >= maxTags ? "Max tags reached" : placeholder}
						disabled={disabled || selectedTags.length >= maxTags}
						className="flex-1 px-3 py-2 bg-transparent border-none outline-none placeholder-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
					/>
					{inputValue && (
						<button
							type="button"
							onClick={() => {
								setInputValue("")
								setHighlightedIndex(-1)
								inputRef.current?.focus()
							}}
							className="mr-2 p-1 hover:bg-gray-100 rounded"
						>
							<X className="h-3 w-3 text-gray-400" />
						</button>
					)}
				</div>

				{/* Dropdown */}
				{isOpen && !disabled && (
					<div
						ref={dropdownRef}
						className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto"
					>
						{suggestions.length > 0 && (
							<div className="p-2">
								<div className="text-xs font-medium text-gray-500 mb-2">
									{inputValue.trim() ? "Suggestions" : "Recent tags"}
								</div>
								{suggestions.map((tag, index) => (
									<button
										key={tag.id}
										type="button"
										onClick={() => handleTagSelect(tag)}
										className={`w-full flex items-center gap-2 px-3 py-2 text-left rounded hover:bg-gray-50 ${
											index === highlightedIndex ? "bg-blue-50 text-blue-700" : ""
										}`}
									>
										<Tag tag={tag} size="small" />
										<span className="text-xs text-gray-500">{tag.usage_count} uses</span>
									</button>
								))}
							</div>
						)}

						{/* Create new tag option */}
						{allowCreate && inputValue.trim() && !wouldCreateDuplicate && (
							<div className="border-t border-gray-100">
								<button
									type="button"
									onClick={handleCreateTag}
									disabled={loading.creating}
									className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 ${
										highlightedIndex === suggestions.length ? "bg-blue-50 text-blue-700" : ""
									}`}
								>
									<Plus className="h-4 w-4 text-green-500" />
									<span>
										Create "{inputValue.trim()}"{loading.creating && " (creating...)"}
									</span>
								</button>
							</div>
						)}

						{/* No suggestions */}
						{suggestions.length === 0 && (!allowCreate || !inputValue.trim() || wouldCreateDuplicate) && (
							<div className="p-4 text-center text-gray-500 text-sm">
								{inputValue.trim() ? "No matching tags found" : "Start typing to search tags"}
							</div>
						)}
					</div>
				)}
			</div>

			{/* Helper text */}
			<div className="mt-1 text-xs text-gray-500">
				{selectedTags.length}/{maxTags} tags selected
				{allowCreate && " • Press Enter to create new tags"}
			</div>
		</div>
	)
}

export default TagInput
