import { useEffect, useState } from "react"

import { api } from "@/lib/apiClient"
import logger from "@/lib/logger"
import { securityMonitor } from "@/utils/securityConfig"
import { AuthContext } from "./AuthContext"

export function AuthProvider({ children }) {
	const [user, setUser] = useState(null)
	const [loading, setLoading] = useState(true)
	const [isAuthenticated, setIsAuthenticated] = useState(false)

	// Inline auth check to avoid unstable function dependencies that cause infinite loops
	// This pattern prevents React's strict dependency checking from triggering re-renders
	useEffect(() => {
		const performAuthCheck = async () => {
			try {
				// Try to get current user - httpOnly cookies are sent automatically
				try {
					const response = await api.get("/auth/me")
					setUser(response)
					setIsAuthenticated(true)
				} catch (authError) {
					// If it's a 401, try to refresh the token first
					if (authError.status === 401) {
						try {
							const refreshResponse = await api.post("/auth/refresh")
							if (refreshResponse?.user) {
								setUser(refreshResponse.user)
								setIsAuthenticated(true)
								return
							}
						} catch (refreshError) {
							logger.error("Auth refresh failed", refreshError)
						}
					}
					setUser(null)
					setIsAuthenticated(false)
				}
			} catch (error) {
				logger.error("Auth check failed", error)
				setUser(null)
				setIsAuthenticated(false)
			} finally {
				setLoading(false)
			}
		}

		performAuthCheck()
	}, [])

	// Set up periodic token refresh for authenticated users
	useEffect(() => {
		if (!isAuthenticated || user?.email === "demo@talimio.com") {
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
					}
				}
			} catch (error) {
				// If refresh fails, check auth again
				if (error.status === 401) {
					setUser(null)
					setIsAuthenticated(false)
				} else {
					logger.error("Token refresh failed", error)
				}
			}
		}, refreshInterval)

		return () => clearInterval(intervalId)
	}, [isAuthenticated, user?.email])

	const login = async (email, password) => {
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
			setIsAuthenticated(true)

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
			setIsAuthenticated(true)

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
		} catch (error) {
			logger.error("Logout failed", error)
		} finally {
			// Clear local state (cookies are cleared by server)
			setUser(null)
			setIsAuthenticated(false)
		}
	}

	const resetPassword = async (email) => {
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
		login,
		signup,
		logout,
		resetPassword,
		// Removed checkAuth and handleTokenExpiration to prevent misuse
	}

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
