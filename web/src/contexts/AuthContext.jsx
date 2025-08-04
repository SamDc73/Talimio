import { createContext, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import useAppStore from "@/stores/useAppStore";
import { securityMonitor } from "@/utils/securityConfig";

export const AuthContext = createContext({});

export const AuthProvider = ({ children }) => {
	const [user, setUser] = useState(null);
	const [loading, setLoading] = useState(true);
	const [isAuthenticated, setIsAuthenticated] = useState(false);
	const [authMode, setAuthMode] = useState("none"); // Default to single-user mode

	// Get app store actions
	const setAppUser = useAppStore((state) => state.setUser);
	const clearAppUser = useAppStore((state) => state.clearUser);

	const checkAuth = useCallback(async () => {
		try {
			// Check if auth is enabled via environment variable
			const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";
			console.log("🔐 Auth check started. Auth enabled:", authEnabled);

			if (!authEnabled) {
				// In single-user mode, set default user and authenticate automatically
				console.log("🔓 Single-user mode: auto-authenticating");
				setUser({
					id: "00000000-0000-0000-0000-000000000001",
					email: "demo@talimio.com",
					username: "Demo User",
				});
				setIsAuthenticated(true);
				setAuthMode("none");
				setLoading(false);
				return;
			}

			// Auth is enabled - check with server (cookies are automatic)
			console.log("🔐 Multi-user mode: checking authentication with server");

			// Try to get current user - httpOnly cookies are sent automatically
			try {
				const response = await api.get("/auth/me");
				console.log("✅ User authenticated:", response.email);
				setUser(response);
				setAppUser(response);
				setIsAuthenticated(true);
				setAuthMode("supabase");
			} catch (authError) {
				// If auth fails, user needs to login
				console.log(
					"❌ Authentication failed:",
					authError.response?.status,
					authError.message,
				);

				// If it's a 401, try to refresh the token first
				if (authError.response?.status === 401) {
					console.log("🔄 Attempting to refresh token due to 401 error");
					try {
						const refreshResponse = await api.post("/auth/refresh");
						if (refreshResponse?.user) {
							console.log("✅ Token refreshed successfully during auth check");
							setUser(refreshResponse.user);
							setAppUser(refreshResponse.user);
							setIsAuthenticated(true);
							setAuthMode("supabase");
							return;
						}
					} catch (refreshError) {
						console.log("❌ Token refresh failed:", refreshError.message);
					}
				}

				clearAppUser();
				setUser(null);
				setIsAuthenticated(false);
				setAuthMode("supabase");
			}
		} catch (error) {
			console.error("💥 Auth check crashed:", error);
			clearAppUser();
			setUser(null);
			setIsAuthenticated(false);
			setAuthMode("supabase");
		} finally {
			setLoading(false);
		}
	}, [setAppUser, clearAppUser]);

	// Check if user is logged in on mount
	useEffect(() => {
		checkAuth();
	}, [checkAuth]);

	// User state updated - future real-time sync can be added here
	useEffect(() => {
		if (user?.id) {
			console.log("✅ User authenticated with ID:", user.id);
			// Future: Add any real-time sync or WebSocket connections here
		}
	}, [user?.id]);

	// Handle token expiration and force re-authentication
	const handleTokenExpiration = useCallback(() => {
		console.log("🔄 Token expired, forcing re-authentication");
		clearAppUser();
		setUser(null);
		setIsAuthenticated(false);

		// Only redirect to auth if we're in multi-user mode
		if (authMode === "supabase") {
			// Small delay to allow state to update
			setTimeout(() => {
				if (window.location.pathname !== "/auth") {
					window.location.href = "/auth";
				}
			}, 100);
		}
	}, [clearAppUser, authMode]);

	// Listen for token expiration events from API client
	useEffect(() => {
		const handleTokenExpired = () => {
			console.log("🚨 Received tokenExpired event from API client");
			handleTokenExpiration();
		};

		window.addEventListener("tokenExpired", handleTokenExpired);
		return () => window.removeEventListener("tokenExpired", handleTokenExpired);
	}, [handleTokenExpiration]);

	// Set up periodic token refresh for authenticated users
	useEffect(() => {
		if (!isAuthenticated || authMode !== "supabase") {
			return;
		}

		// Refresh token 5 minutes before expiry (tokens expire in 60 minutes)
		const refreshInterval = 50 * 60 * 1000; // 50 minutes

		const intervalId = setInterval(async () => {
			try {
				console.log("🔄 Performing periodic token refresh");
				const response = await api.post("/auth/refresh");
				if (response) {
					console.log("✅ Token refreshed successfully");
					// Update user data if it changed
					if (response.user) {
						setUser(response.user);
						setAppUser(response.user);
					}
				}
			} catch (error) {
				console.error("❌ Periodic token refresh failed:", error);
				// If refresh fails, check auth again
				if (error.status === 401) {
					console.log("🔄 Refresh token expired, need to re-authenticate");
					clearAppUser();
					setUser(null);
					setIsAuthenticated(false);
				}
			}
		}, refreshInterval);

		return () => clearInterval(intervalId);
	}, [isAuthenticated, authMode, setAppUser, clearAppUser]);

	const login = useCallback(
		async (email, password) => {
			// Check if auth is enabled
			const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";
			if (!authEnabled) {
				console.warn("Login attempted but auth is disabled");
				return {
					success: false,
					error: "Authentication is not enabled",
				};
			}

			try {
				// Check rate limiting
				if (!securityMonitor.trackLoginAttempt(email, false)) {
					return {
						success: false,
						error: "Too many failed login attempts. Please try again later.",
					};
				}

				const response = await api.post("/auth/login", {
					email,
					password,
				});

				// No need to handle tokens - they're in httpOnly cookies now!
				// Handle the response - it now returns data directly
				const { user } = response;

				// Track successful login
				securityMonitor.trackLoginAttempt(email, true);

				// Update state (no token handling needed)
				setUser(user);
				setAppUser(user);
				setIsAuthenticated(true);
				setAuthMode("supabase");

				console.log("✅ Login successful for:", user.email);

				return { success: true };
			} catch (error) {
				console.error("❌ Login failed:", error);

				// Track failed login
				securityMonitor.trackLoginAttempt(email, false);

				return {
					success: false,
					error: error.data?.detail || error.message || "Login failed",
				};
			}
		},
		[setAppUser],
	);

	const signup = useCallback(
		async (email, password, username) => {
			// Check if auth is enabled
			const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";
			if (!authEnabled) {
				console.warn("Signup attempted but auth is disabled");
				return {
					success: false,
					error: "Authentication is not enabled",
				};
			}

			try {
				const response = await api.post("/auth/signup", {
					email,
					password,
					username,
				});

				// Handle the response - it now returns data directly
				const responseData = response;

				// Check if email confirmation is required
				if (responseData.email_confirmation_required) {
					return {
						success: true,
						emailConfirmationRequired: true,
						message:
							responseData.message ||
							"Please check your email to confirm your account",
					};
				}

				const { user } = responseData;

				// No token handling needed - cookies are set by backend
				// Update state
				setUser(user);
				setAppUser(user);
				setIsAuthenticated(true);
				setAuthMode("supabase");

				return { success: true };
			} catch (error) {
				console.error("Signup failed:", error);
				return {
					success: false,
					error: error.data?.detail || error.message || "Signup failed",
				};
			}
		},
		[setAppUser],
	);

	const logout = useCallback(async () => {
		try {
			// Call logout endpoint (this clears the httpOnly cookie)
			await api.post("/auth/logout");
		} catch (_error) {
			// Ignore errors - logout should always clear local state
			console.log("Logout request failed, clearing local state anyway");
		} finally {
			// Clear local state (cookies are cleared by server)
			clearAppUser();
			setUser(null);
			setIsAuthenticated(false);
		}
	}, [clearAppUser]);

	const resetPassword = useCallback(async (email) => {
		// Check if auth is enabled
		const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";
		if (!authEnabled) {
			return {
				success: false,
				error: "Password reset is not available in single-user mode",
			};
		}

		try {
			const response = await api.post("/auth/reset-password", { email });
			return {
				success: true,
				message:
					response.message || "Password reset instructions sent to your email",
			};
		} catch (error) {
			console.error("Password reset failed:", error);
			return {
				success: false,
				error:
					error.data?.detail || error.message || "Failed to send reset email",
			};
		}
	}, []);

	const value = {
		user,
		loading,
		isAuthenticated,
		authMode,
		login,
		signup,
		logout,
		resetPassword,
		checkAuth,
		handleTokenExpiration,
	};

	// Debug logging
	useEffect(() => {
		console.log("🔐 AuthContext value:", {
			user: user?.email,
			loading,
			isAuthenticated,
			authMode,
			hasLogin: typeof login === "function",
			hasSignup: typeof signup === "function",
			hasLogout: typeof logout === "function",
		});
	}, [user, loading, isAuthenticated, authMode, login, signup, logout]);

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
