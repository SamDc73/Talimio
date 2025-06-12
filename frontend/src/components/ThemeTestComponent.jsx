import { useTheme, useThemeV2 } from "@/contexts/ThemeContext";
import useAppStore from "@/stores/useAppStore";
import React from "react";

/**
 * Component to test theme migration
 * Shows both old and new theme states for comparison
 */
export function ThemeTestComponent() {
	// Old theme system
	const oldTheme = useTheme();

	// New theme system
	const newTheme = useThemeV2();

	// Direct store access
	const storeTheme = useAppStore((state) => state.preferences.theme);
	const toggleTheme = useAppStore((state) => state.toggleTheme);

	return (
		<div className="p-6 border rounded-lg bg-card">
			<h3 className="text-lg font-semibold mb-4">Theme Migration Test</h3>

			<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
				{/* Old Theme System */}
				<div className="space-y-2">
					<h4 className="font-medium">Old Theme System</h4>
					<p className="text-sm text-muted-foreground">
						Current: <span className="font-mono">{oldTheme.theme}</span>
					</p>
					<button
						onClick={() =>
							oldTheme.setTheme(oldTheme.theme === "light" ? "dark" : "light")
						}
						className="px-3 py-1 text-sm bg-primary text-primary-foreground rounded"
					>
						Toggle (Old)
					</button>
				</div>

				{/* New Theme System */}
				<div className="space-y-2">
					<h4 className="font-medium">New Theme System</h4>
					<p className="text-sm text-muted-foreground">
						Current: <span className="font-mono">{newTheme.theme}</span>
					</p>
					<p className="text-sm text-muted-foreground">
						Resolved:{" "}
						<span className="font-mono">{newTheme.resolvedTheme}</span>
					</p>
					<p className="text-sm text-muted-foreground">
						System:{" "}
						<span className="font-mono">
							{newTheme.isSystemTheme ? "Yes" : "No"}
						</span>
					</p>
					<div className="flex gap-1">
						<button
							onClick={() => newTheme.setTheme("light")}
							className="px-2 py-1 text-xs bg-yellow-500 text-white rounded"
						>
							Light
						</button>
						<button
							onClick={() => newTheme.setTheme("dark")}
							className="px-2 py-1 text-xs bg-gray-800 text-white rounded"
						>
							Dark
						</button>
						<button
							onClick={() => newTheme.setTheme("system")}
							className="px-2 py-1 text-xs bg-blue-500 text-white rounded"
						>
							System
						</button>
					</div>
				</div>

				{/* Direct Store Access */}
				<div className="space-y-2">
					<h4 className="font-medium">Direct Store</h4>
					<p className="text-sm text-muted-foreground">
						Store: <span className="font-mono">{storeTheme}</span>
					</p>
					<button
						onClick={toggleTheme}
						className="px-3 py-1 text-sm bg-emerald-600 text-white rounded"
					>
						Cycle Theme
					</button>
				</div>
			</div>

			<div className="mt-4 p-3 bg-muted rounded text-sm">
				<h5 className="font-medium mb-1">Migration Notes:</h5>
				<ul className="text-xs space-y-1 text-muted-foreground">
					<li>• Old system: Only supports 'light' and 'dark'</li>
					<li>• New system: Supports 'light', 'dark', and 'system'</li>
					<li>• Store automatically syncs to API and localStorage</li>
					<li>• System theme follows OS preference automatically</li>
				</ul>
			</div>
		</div>
	);
}
