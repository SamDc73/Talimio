/**
 * Simple API client with common HTTP methods
 */

const BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1";

// Helper function to handle API responses
const handleResponse = async (response) => {
	if (!response.ok) {
		let errorData;
		try {
			errorData = await response.json();
		} catch (_e) {
			errorData = { message: response.statusText };
		}
		const error = new Error(
			`API Error: ${response.status} ${errorData?.message || response.statusText}`,
		);
		error.status = response.status;
		error.data = errorData;
		throw error;
	}

	// Handle responses with no content
	if (
		response.status === 204 ||
		response.headers.get("content-length") === "0"
	) {
		return null;
	}

	return response.json();
};

// Main API client
export const api = {
	async get(endpoint, options = {}) {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			...options,
		});
		return handleResponse(response);
	},

	async post(endpoint, data = null, options = {}) {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			body: data ? JSON.stringify(data) : undefined,
			...options,
		});
		return handleResponse(response);
	},

	async put(endpoint, data = null, options = {}) {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			body: data ? JSON.stringify(data) : undefined,
			...options,
		});
		return handleResponse(response);
	},

	async patch(endpoint, data = null, options = {}) {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: "PATCH",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			body: data ? JSON.stringify(data) : undefined,
			...options,
		});
		return handleResponse(response);
	},

	async delete(endpoint, options = {}) {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: "DELETE",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			...options,
		});
		return handleResponse(response);
	},
};
