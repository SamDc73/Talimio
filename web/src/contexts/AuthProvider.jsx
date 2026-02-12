import { useEffect, useState } from "react"

import { api } from "@/lib/apiClient"
import logger from "@/lib/logger"
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
			const normalizedEmail = email.trim().toLowerCase()

			const formData = new URLSearchParams()
			formData.append("grant_type", "password") // Required by OAuth2 spec
			formData.append("username", normalizedEmail) // OAuth2 spec uses 'username'
			formData.append("password", password)
			const response = await api.post("/auth/login", formData.toString(), {
				headers: { "Content-Type": "application/x-www-form-urlencoded" },
			})

			// No need to handle tokens - they're in httpOnly cookies now!
			// Handle the response - it now returns data directly
			const { user } = response

			// Update state (no token handling needed)
			setUser(user)
			setIsAuthenticated(true)

			return { success: true }
		} catch (error) {
			return {
				success: false,
				error: error.data?.detail || error.message || "Login failed",
			}
		}
	}

	const signup = async (fullName, email, password, username) => {
		try {
			const normalizedFullName = fullName.trim()
			const normalizedEmail = email.trim().toLowerCase()
			const normalizedUsername = (username || "").trim()
			const response = await api.post("/auth/signup", {
				fullName: normalizedFullName,
				email: normalizedEmail,
				password,
				username: normalizedUsername || null,
			})

			// Handle the response - it now returns data directly
			const responseData = response

			// Check if email confirmation is required
			if (responseData.emailConfirmationRequired || !responseData.user) {
				return {
					success: true,
					emailConfirmationRequired: true,
					message: responseData.message || "Signup request received. Please sign in if your account is ready.",
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
			const response = await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() })
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

	const applyPasswordReset = async (token, newPassword) => {
		try {
			const response = await api.post("/auth/reset-password", { token, newPassword })
			return {
				success: true,
				message: response?.message || "Password updated",
			}
		} catch (error) {
			return {
				success: false,
				error: error.data?.detail || error.message || "Failed to reset password",
			}
		}
	}

	const resendVerification = async (email) => {
		try {
			const normalizedEmail = email.trim().toLowerCase()
			const response = await api.post("/auth/resend-verification", { email: normalizedEmail })
			return {
				success: true,
				message: response.message || "If the account exists, a verification email has been sent",
				cooldownSeconds: 60,
			}
		} catch (error) {
			const detail = error.data?.detail
			const detailMessage = typeof detail === "string" ? detail : detail?.message
			return {
				success: false,
				error: detailMessage || error.message || "Failed to resend verification email",
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
		applyPasswordReset,
		resendVerification,
		// Removed checkAuth and handleTokenExpiration to prevent misuse
	}

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
