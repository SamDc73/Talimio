import { createContext, useContext, useEffect, useLayoutEffect } from "react"

import useAppStore from "@/stores/useAppStore"

/**
 * Enhanced ThemeProvider using Zustand for state management
 * Replaces localStorage-based theme persistence with unified store
 */

const ThemeContext = createContext(undefined)

export function ThemeProvider({ children }) {
	// Get theme state and actions from Zustand store with proper selectors
	const theme = useAppStore((state) => state.preferences?.theme ?? "light")
	const updatePreference = useAppStore((state) => state.updatePreference)

	/**
	 * Initialize theme on mount
	 */
	useLayoutEffect(() => {
		// If theme is 'system', resolve to actual system preference
		let resolvedTheme = theme

		if (theme === "system") {
			resolvedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
		}

		// Apply theme to document
		const root = window.document.documentElement
		root.classList.remove("light", "dark")
		root.classList.add(resolvedTheme)
		root.style.colorScheme = resolvedTheme
	}, [theme])

	/**
	 * Listen for system theme changes when theme is set to 'system'
	 */
	useEffect(() => {
		if (theme !== "system") return

		const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")

		const handleChange = (e) => {
			const root = window.document.documentElement
			const resolvedTheme = e.matches ? "dark" : "light"
			root.classList.remove("light", "dark")
			root.classList.add(resolvedTheme)
			root.style.colorScheme = resolvedTheme
		}

		// Support for older browsers
		if (mediaQuery.addEventListener) {
			mediaQuery.addEventListener("change", handleChange)
			return () => mediaQuery.removeEventListener("change", handleChange)
		}
		mediaQuery.addListener(handleChange)
		return () => mediaQuery.removeListener(handleChange)
	}, [theme])

	/**
	 * Provide context value
	 */
	const contextValue = {
		theme,
		setTheme: (newTheme) => {
			if (!newTheme || !["light", "dark", "system"].includes(newTheme)) {
				updatePreference("theme", "system")
				return
			}
			updatePreference("theme", newTheme)
		},
	}

	return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>
}

/**
 * Hook to access theme context
 * @throws {Error} If used outside of ThemeProvider
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
	const context = useContext(ThemeContext)
	if (context === undefined) {
		throw new Error("useTheme must be used within a ThemeProvider")
	}
	return context
}
