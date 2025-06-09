import { useToast } from "@/hooks/use-toast";
import { useCallback, useRef, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

// Helper function to construct the full URL
const buildUrl = (endpoint, pathParams) => {
	let url = `${BASE_URL}${endpoint}`;
	if (pathParams) {
		for (const key of Object.keys(pathParams)) {
			url = url.replace(`{${key}}`, encodeURIComponent(pathParams[key]));
		}
	}
	return url;
};

// Helper function to prepare request options
const prepareRequestOptions = (method, body, customOptions) => {
	const { pathParams, headers, ...restOfCustomOptions } = customOptions;

	const options = {
		method,
		headers: {
			"Content-Type": "application/json",
			// Add other default headers if needed (e.g., Authorization)
			...headers,
		},
		...restOfCustomOptions,
	};

	// Only add body if method allows and body is provided
	if (body && !["GET", "HEAD"].includes(method.toUpperCase())) {
		options.body = JSON.stringify(body);
	}

	return options;
};

// Helper function to handle the API response
const handleResponse = async (response) => {
	if (!response.ok) {
		let errorData;
		try {
			errorData = await response.json();
		} catch (e) {
			// Handle cases where response body is not valid JSON
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
		return null; // Or return an empty object/array based on context
	}

	return response.json(); // Assume JSON response otherwise
};

export function useApi(endpoint, options = {}) {
	const [data, setData] = useState(null);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);
	const { toast } = useToast();
	const abortControllerRef = useRef(null);

	const execute = useCallback(
		async (body = null, callOptions = {}) => {
			// Combine hook options and call-specific options
			const combinedOptions = { ...options, ...callOptions };
			const { method = "GET", pathParams, ...fetchOptions } = combinedOptions;

			// Abort previous request if it's still running
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
			}
			abortControllerRef.current = new AbortController();

			setIsLoading(true);
			setError(null);
			setData(null); // Reset data on new request

			const url = buildUrl(endpoint, pathParams);
			const requestOptions = prepareRequestOptions(method, body, {
				...fetchOptions,
				signal: abortControllerRef.current.signal,
			});

			try {
				const response = await fetch(url, requestOptions);
				const responseData = await handleResponse(response);
				setData(responseData);
				return responseData;
			} catch (err) {
				if (err.name === "AbortError") {
					console.log("Fetch aborted");
					return; // Don't set error state for aborted requests
				}
				setError(err);
				toast({
					title: "API Error",
					description: err.message || "An unexpected error occurred.",
					variant: "destructive",
				});
				// Re-throw the error if the caller needs to handle it further
				throw err;
			} finally {
				setIsLoading(false);
				abortControllerRef.current = null; // Clear the controller
			}
		},
		[endpoint, options, toast], // Dependencies for useCallback
	);

	return { data, isLoading, error, execute };
}
