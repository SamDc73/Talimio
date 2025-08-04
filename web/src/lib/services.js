export const apiClient = {
	async get(endpoint, options = {}) {
		try {
			const response = await fetch(`${endpoint}`, {
				method: "GET",
				headers: {
					"Content-Type": "application/json",
					Accept: "application/json",
				},
				...options,
			});

			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}

			return await response.json();
		} catch (error) {
			console.error("API Request failed:", error);
			if (options.fallbackData) {
				return options.fallbackData;
			}
			throw error;
		}
	},

	async post(endpoint, data, options = {}) {
		try {
			const response = await fetch(`${endpoint}`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Accept: "application/json",
				},
				body: JSON.stringify(data),
				...options,
			});

			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}

			return await response.json();
		} catch (error) {
			console.error("API Request failed:", error);
			if (options.fallbackData) {
				return options.fallbackData;
			}
			throw error;
		}
	},
};
