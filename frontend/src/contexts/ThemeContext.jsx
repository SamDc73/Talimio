import useAppStore from "@/stores/useAppStore";
import React, { createContext, useContext, useEffect } from "react";

/**
 * Enhanced ThemeProvider using Zustand for state management
 * Replaces localStorage-based theme persistence with unified store
 */

const ThemeContext = createContext(undefined);

export function ThemeProvider({ children }) {
	// Get theme state and actions from Zustand store
	const theme = useAppStore((state) => state.preferences.theme);
	const updatePreference = useAppStore((state) => state.updatePreference);
	const toggleTheme = useAppStore((state) => state.toggleTheme);

	/**
	 * Initialize theme on mount
	 */
	useEffect(() => {
		// If theme is 'system', resolve to actual system preference
		let resolvedTheme = theme;

		if (theme === "system") {
			resolvedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
				? "dark"
				: "light";
		}

		// Apply theme to document
		const root = window.document.documentElement;
		root.classList.remove("light", "dark");
		root.classList.add(resolvedTheme);
	}, [theme]);

	/**
	 * Listen for system theme changes when using 'system' theme
	 */
	useEffect(() => {
		if (theme !== "system") return;

		const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

		const handleSystemThemeChange = (e) => {
			const root = window.document.documentElement;
			root.classList.remove("light", "dark");
			root.classList.add(e.matches ? "dark" : "light");
		};

		mediaQuery.addEventListener("change", handleSystemThemeChange);

		return () => {
			mediaQuery.removeEventListener("change", handleSystemThemeChange);
		};
	}, [theme]);

	/**
	 * Enhanced setTheme that supports 'system' option
	 */
	const setTheme = (newTheme) => {
		updatePreference("theme", newTheme);
	};

	/**
	 * Get the resolved theme (actual light/dark, not 'system')
	 */
	const getResolvedTheme = () => {
		if (theme === "system") {
			return window.matchMedia("(prefers-color-scheme: dark)").matches
				? "dark"
				: "light";
		}
		return theme;
	};

	const contextValue = {
		theme,
		setTheme,
		toggleTheme,
		resolvedTheme: getResolvedTheme(),
		isSystemTheme: theme === "system",
	};

	return (
		<ThemeContext.Provider value={contextValue}>
			{children}
		</ThemeContext.Provider>
	);
}

/**
 * Hook to use theme context
 */
export function useTheme() {
	const context = useContext(ThemeContext);
	if (context === undefined) {
		throw new Error("useTheme must be used within a ThemeProvider");
	}
	return context;
}

// Keep V2 export for backwards compatibility
export const useThemeV2 = useTheme;

/**
 * Hook that provides both old and new theme interfaces during migration
 */
export function useThemeMigrationBridge() {
	const newTheme = useTheme();

	// Provide old interface for backwards compatibility
	const oldInterface = {
		theme: newTheme.resolvedTheme, // Old interface expects 'light' or 'dark', not 'system'
		setTheme: newTheme.setTheme,
	};

	return {
		// New enhanced interface
		...newTheme,
		// Old interface for compatibility
		legacy: oldInterface,
	};
}

// Also export V2 variant for backwards compatibility
export const ThemeProviderV2 = ThemeProvider;
