import React from "react"

/**
 * Development-time utility to check for nested interactive elements
 *
 * This function recursively checks React elements for nested interactive elements
 * (buttons, links, inputs, etc.) and logs warnings to help prevent accessibility
 * issues and render loops.
 *
 * @param {React.ReactElement} element - The React element to check
 * @param {string[]} parentPath - Array of parent element types (for error reporting)
 */
export function checkNestedInteractiveElements(element, parentPath = []) {
	if (process.env.NODE_ENV !== "development") return

	// Interactive element types that shouldn't be nested
	const interactiveElements = ["button", "a", "input", "select", "textarea"]

	// Get element type as string
	const getElementType = (el) => {
		if (typeof el.type === "string") return el.type
		if (el.type?.displayName) return el.type.displayName
		if (el.type?.name) return el.type.name
		return "Component"
	}

	const elementType = getElementType(element)
	const isInteractive = interactiveElements.includes(elementType.toLowerCase())

	// Check if we have nested interactive elements
	if (isInteractive && parentPath.some((parent) => interactiveElements.includes(parent.toLowerCase()))) {
		const _parentInteractive = parentPath.find((parent) => interactiveElements.includes(parent.toLowerCase()))
	}

	// Recursively check children
	const newPath = isInteractive ? [...parentPath, elementType] : parentPath

	React.Children.forEach(element.props?.children, (child) => {
		if (React.isValidElement(child)) {
			checkNestedInteractiveElements(child, newPath)
		}
	})
}

/**
 * HOC to wrap components with nested interactive element checking
 *
 * Usage:
 * export default withInteractiveCheck(MyComponent);
 *
 * @param {React.ComponentType} Component - Component to wrap
 * @returns {React.ComponentType} - Wrapped component
 */
export function withInteractiveCheck(component) {
	if (process.env.NODE_ENV !== "development") {
		return component
	}

	const WrappedComponent = (props) => {
		const element = <component {...props} />

		// Check on mount and updates
		React.useEffect(() => {
			if (React.isValidElement(element)) {
				checkNestedInteractiveElements(element)
			}
		})

		return element
	}

	WrappedComponent.displayName = `withInteractiveCheck(${component.displayName || component.name || "Component"})`

	return WrappedComponent
}

/**
 * Hook to check a component's render output for nested interactive elements
 *
 * Usage:
 * function MyComponent() {
 *   const checkElement = useInteractiveCheck();
 *   return checkElement(<div>...</div>);
 * }
 *
 * @returns {Function} - Function that checks and returns the element
 */
export function useInteractiveCheck() {
	if (process.env.NODE_ENV !== "development") {
		return (element) => element
	}

	// Return a function that immediately checks the element without using hooks
	return (element) => {
		if (React.isValidElement(element)) {
			checkNestedInteractiveElements(element)
		}
		return element
	}
}
