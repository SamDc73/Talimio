import { create } from "zustand"
import { devtools } from "zustand/middleware"
import { immer } from "zustand/middleware/immer"

import { api } from "@/lib/apiClient"

/**
 * Tag store for managing user tags and tag-content associations
 */
const useTagStore = create(
	devtools(
		immer((set, get) => ({
			// ========== STATE ==========
			// All user tags: { [tagId]: Tag }
			tags: {},
			// Tag loading states
			loading: {
				tags: false,
				creating: false,
				updating: false,
				deleting: false,
			},
			// Content tags: { [contentType]: { [contentId]: [tagIds] } }
			contentTags: {},
			// Recently used tags for quick access
			recentTags: [],
			// Tag filters
			filters: {
				category: null,
				searchQuery: "",
			},

			// ========== ACTIONS ==========

			// User Tags Management
			async fetchUserTags() {
				set((state) => {
					state.loading.tags = true
				})

				try {
					const tags = await api.get("/tags/tags")

					set((state) => {
						state.tags = {}
						for (const tag of tags) {
							state.tags[tag.id] = tag
						}
						state.loading.tags = false
					})

					return tags
				} catch (error) {
					set((state) => {
						state.loading.tags = false
					})
					throw error
				}
			},

			async createTag(tagData) {
				set((state) => {
					state.loading.creating = true
				})

				try {
					// In our backend, tags are created automatically when updating content tags
					// So we'll create a mock tag object and let the backend handle creation
					const mockTag = {
						id: `temp_${Date.now()}`,
						name: tagData.name,
						category: tagData.category || null,
						color: tagData.color || null,
						usage_count: 0,
						created_at: new Date().toISOString(),
						updated_at: new Date().toISOString(),
					}

					set((state) => {
						state.tags[mockTag.id] = mockTag
						state.loading.creating = false
						// Add to recent tags
						state.recentTags.unshift(mockTag.id)
						if (state.recentTags.length > 10) {
							state.recentTags = state.recentTags.slice(0, 10)
						}
					})

					return mockTag
				} catch (error) {
					set((state) => {
						state.loading.creating = false
					})
					throw error
				}
			},

			async updateTag(_tagId, _updateData) {
				return null
			},

			async deleteTag(_tagId) {
				return null
			},

			// Content Tagging
			async fetchContentTags(contentType, contentId) {
				// Normalize content type to match backend expectations
				const normalizedType = get()._normalizeContentType(contentType)
				if (!normalizedType) {
					throw new Error(`Unsupported content type: ${contentType}`)
				}

				const tags = await api.get(`/tags/${normalizedType}/${contentId}/tags`)

				set((state) => {
					if (!state.contentTags[contentType]) {
						state.contentTags[contentType] = {}
					}
					state.contentTags[contentType][contentId] = tags.map((tag) => tag.id)

					// Cache tag objects
					for (const tag of tags) {
						state.tags[tag.id] = tag
					}
				})

				return tags
			},

			async updateContentTags(contentType, contentId, tagNames) {
				// Normalize content type to match backend expectations
				const normalizedType = get()._normalizeContentType(contentType)
				if (!normalizedType) {
					throw new Error(`Unsupported content type: ${contentType}`)
				}

				const result = await api.put(`/tags/${normalizedType}/${contentId}/tags`, {
					tags: tagNames,
				})

				// Refresh content tags
				await get().fetchContentTags(contentType, contentId)

				return result
			},

			// Utilities
			getFilteredTags() {
				const { tags, filters } = get()
				let filteredTags = Object.values(tags)

				if (filters.category) {
					filteredTags = filteredTags.filter((tag) => tag.category === filters.category)
				}

				if (filters.searchQuery) {
					const query = filters.searchQuery.toLowerCase()
					filteredTags = filteredTags.filter((tag) => tag.name.toLowerCase().includes(query))
				}

				return filteredTags.toSorted((a, b) => b.usage_count - a.usage_count)
			},

			getRecentTags() {
				const { tags, recentTags } = get()
				return recentTags
					.map((tagId) => tags[tagId])
					.filter(Boolean)
					.slice(0, 5)
			},

			getContentTagObjects(contentType, contentId) {
				const { tags, contentTags } = get()
				const tagIds = contentTags[contentType]?.[contentId] || []
				return tagIds.map((tagId) => tags[tagId]).filter(Boolean)
			},

			// Filters
			setFilter(key, value) {
				set((state) => {
					state.filters[key] = value
				})
			},

			clearFilters() {
				set((state) => {
					state.filters = {
						category: null,
						searchQuery: "",
					}
				})
			},

			// Helper method to normalize content types for API calls
			_normalizeContentType(contentType) {
				const supportedTypes = {
					youtube: "video",
					course: "course",
					book: "book",
					video: "video",
				}
				return supportedTypes[contentType] || null
			},

			// Quick tag operations
			addToRecentTags(tagId) {
				set((state) => {
					// Remove if already exists
					state.recentTags = state.recentTags.filter((id) => id !== tagId)
					// Add to front
					state.recentTags.unshift(tagId)
					// Keep only 10 most recent
					if (state.recentTags.length > 10) {
						state.recentTags = state.recentTags.slice(0, 10)
					}
				})
			},
		})),
		{
			name: "tag-store",
		}
	)
)

export default useTagStore
