const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

class ApiClient {
	constructor() {
		this.defaults = {
			headers: {
				common: {},
			},
		};
	}

	async request(url, options = {}) {
		const headers = {
			"Content-Type": "application/json",
			...this.defaults.headers.common,
			...options.headers,
		};

		const response = await fetch(`${BASE_URL}${url}`, {
			...options,
			headers,
		});

		if (!response.ok) {
			const error = new Error(`HTTP error! status: ${response.status}`);
			error.response = {
				data: await response.json().catch(() => ({})),
				status: response.status,
			};
			throw error;
		}

		// Check if response has content (status 204 means no content)
		const hasContent = response.status !== 204 && response.headers.get("content-length") !== "0";
		
		return {
			data: hasContent ? await response.json() : null,
			status: response.status,
		};
	}

	async get(url, options) {
		return this.request(url, { ...options, method: "GET" });
	}

	async post(url, data, options) {
		return this.request(url, {
			...options,
			method: "POST",
			body: JSON.stringify(data),
		});
	}

	async put(url, data, options) {
		return this.request(url, {
			...options,
			method: "PUT",
			body: JSON.stringify(data),
		});
	}

	async delete(url, options) {
		return this.request(url, { ...options, method: "DELETE" });
	}
}

const api = new ApiClient();

export default api;
