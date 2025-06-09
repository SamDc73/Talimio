const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const videoApi = {
	async createVideo(youtubeUrl) {
		const response = await fetch(`${BASE_URL}/videos`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ url: youtubeUrl }),
		});

		if (!response.ok) {
			if (response.status === 409) {
				// Video already exists, but that's OK - treat as success
				const data = await response.json();
				return data;
			}
			const error = await response
				.json()
				.catch(() => ({ detail: "Failed to create video" }));
			throw new Error(error.detail || "Failed to create video");
		}

		return response.json();
	},

	async getVideos(params = {}) {
		const queryString = new URLSearchParams(params).toString();
		const url = queryString
			? `${BASE_URL}/videos?${queryString}`
			: `${BASE_URL}/videos`;

		const response = await fetch(url);

		if (!response.ok) {
			throw new Error("Failed to fetch videos");
		}

		return response.json();
	},

	async getVideo(id) {
		const response = await fetch(`${BASE_URL}/videos/${id}`);

		if (!response.ok) {
			throw new Error("Failed to fetch video");
		}

		return response.json();
	},

	async updateVideo(id, data) {
		const response = await fetch(`${BASE_URL}/videos/${id}`, {
			method: "PATCH",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(data),
		});

		if (!response.ok) {
			throw new Error("Failed to update video");
		}

		return response.json();
	},

	async updateProgress(id, progressData) {
		const response = await fetch(`${BASE_URL}/videos/${id}/progress`, {
			method: "PATCH",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(progressData),
		});

		if (!response.ok) {
			throw new Error("Failed to update progress");
		}

		return response.json();
	},

	async deleteVideo(id) {
		const response = await fetch(`${BASE_URL}/videos/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete video");
		}
	},
};
