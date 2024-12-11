import { useState, useCallback } from 'react';
import { apiClient } from '../lib/services';

export function useApi(defaultEndpoint, options = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const execute = useCallback(async (body = null, customOptions = {}) => {
    try {
      setIsLoading(true);
      setError(null);

      const url = customOptions.url || defaultEndpoint;
      const method = customOptions.method || options.method || 'GET';
      const requestOptions = { ...options, ...customOptions };

      let response;
      switch (method.toUpperCase()) {
        case 'GET':
          response = await apiClient.get(url, requestOptions);
          break;
        case 'POST':
          response = await apiClient.post(url, body, requestOptions);
          break;
        case 'PUT':
          response = await apiClient.put(url, body, requestOptions);
          break;
        case 'DELETE':
          response = await apiClient.delete(url, requestOptions);
          break;
        default:
          response = await apiClient.get(url, requestOptions);
      }

      setData(response);
      return response;
    } catch (err) {
      console.error('API Error:', err);
      setError(err);

      if (err.status === 422) {
        throw new Error(`Validation error: ${err.data?.detail?.[0]?.msg || 'Invalid input'}`);
      }

      if (options.fallbackData) {
        console.warn('Using fallback data due to API error:', err);
        const fallbackResult = typeof options.fallbackData === 'function'
          ? options.fallbackData(body, customOptions)
          : options.fallbackData;
        setData(fallbackResult);
        return fallbackResult;
      }

      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [defaultEndpoint, options]);

  return {
    data,
    error,
    isLoading,
    execute
  };
}
