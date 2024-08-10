import { supabase } from "@/lib/supabase"

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1"

// Helper to get auth headers
async function getAuthHeaders() {
	const headers = {}

	// Get the Supabase session
	const {
		data: { session },
	} = await supabase.auth.getSession()
	if (session?.access_token) {
		headers.Authorization = `Bearer ${session.access_token}`
	}

	return headers
}

export const booksApi = {
	async getBook(bookId) {
		const authHeaders = await getAuthHeaders()

		const response = await fetch(`${BASE_URL}/books/${bookId}`, {
			headers: authHeaders,
			credentials: "include", // Include cookies for authentication
		})

		if (!response.ok) {
			if (response.status === 404) {
				throw new Error(`Book not found. The book you're looking for doesn't exist or has been removed.`)
			}
			throw new Error(`Failed to fetch book (${response.status} ${response.statusText})`)
		}

		return response.json()
	},

	async updateProgress(bookId, progressData) {
		const authHeaders = await getAuthHeaders()

		const response = await fetch(`${BASE_URL}/books/${bookId}/progress`, {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
				...authHeaders,
			},
			credentials: "include", // Include cookies for authentication
			body: JSON.stringify(progressData),
		})

		if (!response.ok) {
			throw new Error("Failed to update book progress")
		}

		return response.json()
	},
}
