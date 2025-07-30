import React from "react";

// Version compatibility check
const checkReactVersion = () => {
	const reactVersion = React.version;

	// Check for React 19
	if (reactVersion.startsWith("19")) {
		// Check for specific APIs we're using
		const requiredReactAPIs = [
			"Fragment",
			"forwardRef",
			"useState",
			"useEffect",
		];
		const missingAPIs = requiredReactAPIs.filter((api) => !React[api]);

		if (missingAPIs.length > 0) {
			console.warn("[Warning] Missing required React APIs:", missingAPIs);
		}
	}
};

// Check Radix UI component availability
const checkRadixComponents = async () => {
	try {
		const tooltipModule = await import("@radix-ui/react-tooltip");
		const radioGroupModule = await import("@radix-ui/react-radio-group");
		const separatorModule = await import("@radix-ui/react-separator");

		// Verify all components loaded successfully
		return !!(
			tooltipModule.TooltipProvider &&
			radioGroupModule.Root &&
			separatorModule.Root
		);
	} catch (error) {
		console.error("[Error] Failed to load Radix UI components:", error);
		return false;
	}
};

export { checkReactVersion, checkRadixComponents };
