/**
 * Global MDX compilation cache
 * Stores compiled MDX components to prevent recompilation
 * React 19 compatible - no memoization needed
 */
class MdxCache {
	constructor() {
		this.cache = new Map()
		this.compiling = new Map()
	}

	/**
	 * Get a unique key for the content
	 */
	getKey(content) {
		if (!content) return "empty"

		// Create a more robust hash using content length, first/last chars, and checksum
		const start = content.substring(0, 50)
		const end = content.substring(Math.max(0, content.length - 50))
		const middle = content.substring(Math.floor(content.length / 2), Math.floor(content.length / 2) + 10)

		// Simple checksum for collision detection
		let checksum = 0
		for (let i = 0; i < content.length; i += Math.max(1, Math.floor(content.length / 100))) {
			checksum += content.charCodeAt(i)
		}

		return `${start}_${middle}_${end}_${content.length}_${checksum}`
	}

	/**
	 * Check if content is cached
	 */
	has(content) {
		return this.cache.has(this.getKey(content))
	}

	/**
	 * Get cached component
	 */
	get(content) {
		return this.cache.get(this.getKey(content))
	}

	/**
	 * Set cached component
	 */
	set(content, component) {
		const key = this.getKey(content)
		this.cache.set(key, component)
		this.compiling.delete(key)
	}

	/**
	 * Check if content is currently being compiled
	 */
	isCompiling(content) {
		return this.compiling.has(this.getKey(content))
	}

	/**
	 * Mark content as being compiled
	 */
	setCompiling(content, promise) {
		this.compiling.set(this.getKey(content), promise)
	}

	/**
	 * Get the compilation promise
	 */
	getCompiling(content) {
		return this.compiling.get(this.getKey(content))
	}

	/**
	 * Clear cache (for development/debugging)
	 */
	clear() {
		this.cache.clear()
		this.compiling.clear()
	}

	/**
	 * Get cache stats
	 */
	getStats() {
		return {
			cached: this.cache.size,
			compiling: this.compiling.size,
			total: this.cache.size + this.compiling.size,
		}
	}
}

// Export singleton instance
export const mdxCache = new MdxCache()

// For debugging in development
if (process.env.NODE_ENV === "development") {
	window.mdxCache = mdxCache
}
