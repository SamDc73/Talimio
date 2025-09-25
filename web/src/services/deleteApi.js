import { api } from "@/lib/apiClient"

export const deleteApi = {
	async deleteVideo(id) {
		return this.deleteItem("youtube", id)
	},

	async deleteBook(id) {
		return this.deleteItem("book", id)
	},

	async deleteCourse(id) {
		return this.deleteItem("course", id)
	},

	async deleteItem(itemType, id) {
		// Map web app item types to backend content types
		const contentTypeMap = {
			video: "youtube",
			youtube: "youtube",
			book: "book",
			course: "course",
			roadmap: "course",
		}

		const contentType = contentTypeMap[itemType] || itemType

		try {
			const response = await api.delete(`/content/${contentType}/${id}`)
			// DELETE endpoints typically return 204 No Content, which is a success
			return response
		} catch (error) {
			const errorMsg = error.response?.data?.detail || `Failed to delete ${itemType}`
			throw new Error(errorMsg)
		}
	},
}
