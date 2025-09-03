/**
 * Feature flags configuration for platform/OSS mode
 * Controls which features are available based on deployment mode
 */

// Deployment mode: 'oss' for self-hosted, 'cloud' for SaaS platform
export const PLATFORM_MODE = import.meta.env.VITE_PLATFORM_MODE || "oss"

// Feature flags based on deployment mode
export const FEATURES = {
	// Platform-only features (hidden in OSS mode)
	BILLING: PLATFORM_MODE === "cloud",
	SUBSCRIPTIONS: PLATFORM_MODE === "cloud",
	USAGE_LIMITS: PLATFORM_MODE === "cloud",
	ADMIN_DASHBOARD: PLATFORM_MODE === "cloud",
	TEAM_COLLABORATION: PLATFORM_MODE === "cloud",
	ADVANCED_ANALYTICS: PLATFORM_MODE === "cloud",

	// Payment integration
	STRIPE_ENABLED: PLATFORM_MODE === "cloud" && import.meta.env.VITE_STRIPE_KEY,

	// Storage limits
	MAX_STORAGE_GB: PLATFORM_MODE === "cloud" ? 100 : null, // null = unlimited for self-hosted
	MAX_UPLOADS_PER_DAY: PLATFORM_MODE === "cloud" ? 50 : null,

	// AI features
	AI_CREDITS_ENABLED: PLATFORM_MODE === "cloud",
	UNLIMITED_AI: PLATFORM_MODE === "oss", // Self-hosters use their own API keys

	// Authentication
	SSO_ENABLED: PLATFORM_MODE === "cloud",
	MAGIC_LINK_AUTH: PLATFORM_MODE === "cloud",

	// Support & Community
	SUPPORT_CHAT: PLATFORM_MODE === "cloud",
	COMMUNITY_FEATURES: PLATFORM_MODE === "cloud",
}

// Helper function to check if a feature is enabled
export const isFeatureEnabled = (feature) => {
	return FEATURES[feature] === true
}

// Helper to get platform-specific configuration
export const getPlatformConfig = () => ({
	mode: PLATFORM_MODE,
	isCloud: PLATFORM_MODE === "cloud",
	isOSS: PLATFORM_MODE === "oss",
	features: FEATURES,
})
