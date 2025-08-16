// For backward compatibility - components using the old provider pattern
// will just get a no-op provider
export function TextSelectionProvider({ children }) {
	return children
}

// For backward compatibility - returns no-op function
export const useTextSelection = () => {
	return {
		setSelectionHandlers: () => {
			// No-op for backward compatibility
		},
	}
}
