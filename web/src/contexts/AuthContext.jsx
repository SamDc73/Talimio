import { createContext, useEffect, useRef, useState } from "react"

import { api } from "@/lib/apiClient"
import useAppStore from "@/stores/useAppStore"
import { securityMonitor } from "@/utils/securityConfig"

export const AuthContext = createContext({})

export const AuthProvider = ({ children }) => {
	const [user, setUser] = useState(null)
	const [loading, setLoading] = useState(true)
	const [isAuthenticated, setIsAuthenticated] = useState(false)
	const [authMode, setAuthMode] = useState("none") // Default to single-user mode

	// Get app store actions
	const setAppUser = useAppStore((state) => state.setUser)
	const clearAppUser = useAppStore((state) => state.clearUser)

	// Inline auth check to avoid unstable function dependencies that cause infinite loops
	// This pattern prevents React's strict dependency checking from triggering re-renders
	useEffect(() => {
		const performAuthCheck = async () => {
			try {
				// Check if auth is enabled via environment variable
				const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"

				if (!authEnabled) {
					setUser({
						id: "00000000-0000-0000-0000-000000000001",
						email: "demo@talimio.com",
						username: "Demo User",
					})
					setIsAuthenticated(true)
					setAuthMode("none")
					setLoading(false)
					return
				}

				// Try to get current user - httpOnly cookies are sent automatically
				try {
					const response = await api.get("/auth/me")
					setUser(response)
					setAppUser(response)
					setIsAuthenticated(true)
					setAuthMode("supabase")
				} catch (authError) {
					// If it's a 401, try to refresh the token first
					if (authError.status === 401) {
						try {
							const refreshResponse = await api.post("/auth/refresh")
							if (refreshResponse?.user) {
								setUser(refreshResponse.user)
								setAppUser(refreshResponse.user)
								setIsAuthenticated(true)
								setAuthMode("supabase")
								return
							}
						} catch (_refreshError) {}
					}
					clearAppUser()
					setUser(null)
					setIsAuthenticated(false)
					setAuthMode("supabase")
				}
			} catch (_error) {
				clearAppUser()
				setUser(null)
				setIsAuthenticated(false)
				setAuthMode("supabase")
			} finally {
				setLoading(false)
			}
		}

		performAuthCheck()
	}, [clearAppUser, setAppUser])

	// User state updated - future real-time sync can be added here
	useEffect(() => {
		if (user?.id) {
			// Future: Add any real-time sync or WebSocket connections here
		}
	}, [user?.id])

	// Ref pattern prevents function recreation on every render while still accessing current state
	// Without this, adding the function to useEffect deps would cause infinite loops
	const handleTokenExpirationRef = useRef()

	useEffect(() => {
		handleTokenExpirationRef.current = () => {
			clearAppUser()
			setUser(null)
			setIsAuthenticated(false)

			// Only redirect to auth if we're in multi-user mode
			if (authMode === "supabase") {
				// Small delay to allow state to update
				setTimeout(() => {
					if (window.location.pathname !== "/auth") {
						window.location.href = "/auth"
					}
				}, 100)
			}
		}
	}, [authMode, clearAppUser])

	// Listen for token expiration events from API client
	useEffect(() => {
		const handleTokenExpired = () => {
			if (handleTokenExpirationRef.current) {
				handleTokenExpirationRef.current()
			}
		}

		window.addEventListener("tokenExpired", handleTokenExpired)
		return () => window.removeEventListener("tokenExpired", handleTokenExpired)
	}, [])

	// Set up periodic token refresh for authenticated users
	useEffect(() => {
		if (!isAuthenticated || authMode !== "supabase") {
			return
		}

		// Refresh token 5 minutes before expiry (tokens expire in 60 minutes)
		const refreshInterval = 50 * 60 * 1000 // 50 minutes

		const intervalId = setInterval(async () => {
			try {
				const response = await api.post("/auth/refresh")
				if (response) {
					// Update user data if it changed
					if (response.user) {
						setUser(response.user)
						setAppUser(response.user)
					}
				}
			} catch (error) {
				// If refresh fails, check auth again
				if (error.status === 401) {
					clearAppUser()
					setUser(null)
					setIsAuthenticated(false)
				}
			}
		}, refreshInterval)

		return () => clearInterval(intervalId)
	}, [isAuthenticated, authMode, setAppUser, clearAppUser])

	const login = async (email, password) => {
		// Check if auth is enabled
		const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"
		if (!authEnabled) {
			return {
				success: false,
				error: "Authentication is not enabled",
			}
		}

		try {
			// Check rate limiting
			if (!securityMonitor.trackLoginAttempt(email, false)) {
				return {
					success: false,
					error: "Too many failed login attempts. Please try again later.",
				}
			}

			const response = await api.post("/auth/login", {
				email,
				password,
			})

			// No need to handle tokens - they're in httpOnly cookies now!
			// Handle the response - it now returns data directly
			const { user } = response

			// Track successful login
			securityMonitor.trackLoginAttempt(email, true)

			// Update state (no token handling needed)
			setUser(user)
			setAppUser(user)
			setIsAuthenticated(true)
			setAuthMode("supabase")

			return { success: true }
		} catch (error) {
			// Track failed login
			securityMonitor.trackLoginAttempt(email, false)

			return {
				success: false,
				error: error.data?.detail || error.message || "Login failed",
			}
		}
	}

	const signup = async (email, password, username) => {
		// Check if auth is enabled
		const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"
		if (!authEnabled) {
			return {
				success: false,
				error: "Authentication is not enabled",
			}
		}

		try {
			const response = await api.post("/auth/signup", {
				email,
				password,
				username,
			})

			// Handle the response - it now returns data directly
			const responseData = response

			// Check if email confirmation is required
			if (responseData.email_confirmation_required) {
				return {
					success: true,
					emailConfirmationRequired: true,
					message: responseData.message || "Please check your email to confirm your account",
				}
			}

			const { user } = responseData

			// No token handling needed - cookies are set by backend
			// Update state
			setUser(user)
			setAppUser(user)
			setIsAuthenticated(true)
			setAuthMode("supabase")

			return { success: true }
		} catch (error) {
			return {
				success: false,
				error: error.data?.detail || error.message || "Signup failed",
			}
		}
	}

	const logout = async () => {
		try {
			// Call logout endpoint (this clears the httpOnly cookie)
			await api.post("/auth/logout")
		} catch (_error) {
		} finally {
			// Clear local state (cookies are cleared by server)
			clearAppUser()
			setUser(null)
			setIsAuthenticated(false)
		}
	}

	const resetPassword = async (email) => {
		// Check if auth is enabled
		const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"
		if (!authEnabled) {
			return {
				success: false,
				error: "Password reset is not available in single-user mode",
			}
		}

		try {
			const response = await api.post("/auth/reset-password", { email })
			return {
				success: true,
				message: response.message || "Password reset instructions sent to your email",
			}
		} catch (error) {
			return {
				success: false,
				error: error.data?.detail || error.message || "Failed to send reset email",
			}
		}
	}

	const value = {
		user,
		loading,
		isAuthenticated,
		authMode,
		login,
		signup,
		logout,
		resetPassword,
		// Removed checkAuth and handleTokenExpiration to prevent misuse
	}

	// Debug logging
	useEffect(() => {}, [])

	return <AuthContext value={value}>{children}</AuthContext>
}
