import {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useState,
} from "react";

/**
 * Context for managing the course navigation sidebar state
 * Provides functionality to control sidebar visibility throughout the application
 */
const SidebarContext = createContext(null);

/**
 * Provider component that makes sidebar state available to any nested component
 * Initializes the sidebar as open by default and provides a memoized state
 * to prevent unnecessary re-renders
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components that will have access to sidebar state
 */
export function SidebarProvider({ children }) {
	const [isOpen, setIsOpen] = useState(true); // Default to open

	// Stable reference for toggle function
	const toggleSidebar = useCallback(() => {
		setIsOpen((prevIsOpen) => !prevIsOpen);
	}, []);

	// Memoized value to prevent unnecessary re-renders
	const value = useMemo(
		() => ({
			isOpen,
			toggleSidebar,
		}),
		[isOpen, toggleSidebar],
	);

	return (
		<SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
	);
}

/**
 * Hook for components to access the sidebar context
 * @returns {Object} { isOpen, toggleSidebar }
 */
export function useSidebar() {
	const context = useContext(SidebarContext);
	if (context === null) {
		throw new Error("useSidebar must be used within a SidebarProvider");
	}
	return context;
}
