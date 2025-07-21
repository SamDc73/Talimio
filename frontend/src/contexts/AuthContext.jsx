import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import api from "@/services/api";

const AuthContext = createContext({});

export const useAuth = () => {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within an AuthProvider");
	}
	return context;
};

export const AuthProvider = ({ children }) => {
	const [user, setUser] = useState(null);
	const [loading, setLoading] = useState(true);
	const [isAuthenticated, setIsAuthenticated] = useState(false);
	const [authMode, setAuthMode] = useState("none"); // Default to single-user mode

	const checkAuth = useCallback(async () => {
		try {
			// Check if auth is enabled via environment variable
			const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";

			if (!authEnabled) {
				// In single-user mode, set default user
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

			// Auth is enabled - check for valid token
			const token = localStorage.getItem("access_token");
			if (token) {
				// Set token in API headers if available
				api.defaults.headers.common.Authorization = `Bearer ${token}`;
			}

			// Try to get current user - this will work in auth mode
			try {
				const response = await api.get("/auth/me");
				setUser(response.data);
				setIsAuthenticated(true);
				setAuthMode("supabase"); // If /auth/me works, we're in Supabase mode
			} catch (authError) {
				// If auth fails, clear token and stay unauthenticated
				// 401 is expected when not logged in, so we don't log it as an error
				if (authError.response?.status !== 401) {
					console.log("Auth validation failed:", authError.message);
				}
				localStorage.removeItem("access_token");
				delete api.defaults.headers.common.Authorization;
				setUser(null);
				setIsAuthenticated(false);
				setAuthMode("supabase");
			}
		} catch (error) {
			console.error("Auth check failed:", error);
			localStorage.removeItem("access_token");
			delete api.defaults.headers.common.Authorization;
			setUser(null);
			setIsAuthenticated(false);
		} finally {
			setLoading(false);
		}
	}, []);

	// Check if user is logged in on mount
	useEffect(() => {
		checkAuth();
	}, [checkAuth]);

	const login = async (email, password) => {
		try {
			const response = await api.post("/auth/login", {
				email,
				password,
			});

			const { access_token, user } = response.data;

			// Store token
			localStorage.setItem("access_token", access_token);
			api.defaults.headers.common.Authorization = `Bearer ${access_token}`;

			// Update state
			setUser(user);
			setIsAuthenticated(true);
			setAuthMode("supabase");

			return { success: true };
		} catch (error) {
			console.error("Login failed:", error);
			return {
				success: false,
				error: error.response?.data?.detail || "Login failed",
			};
		}
	};

	const signup = async (email, password, username) => {
		try {
			const response = await api.post("/auth/signup", {
				email,
				password,
				username,
			});

			// Check if email confirmation is required
			if (response.data.email_confirmation_required) {
				return {
					success: true,
					emailConfirmationRequired: true,
					message:
						response.data.message ||
						"Please check your email to confirm your account",
				};
			}

			const { access_token, user } = response.data;

			// Store token
			localStorage.setItem("access_token", access_token);
			api.defaults.headers.common.Authorization = `Bearer ${access_token}`;

			// Update state
			setUser(user);
			setIsAuthenticated(true);
			setAuthMode("supabase");

			return { success: true };
		} catch (error) {
			console.error("Signup failed:", error);
			return {
				success: false,
				error: error.response?.data?.detail || "Signup failed",
			};
		}
	};

	const logout = async () => {
		try {
			await api.post("/auth/logout");
		} catch (_error) {
			// Ignore errors - logout should always clear local state
			console.log("Logout request failed, clearing local state anyway");
		} finally {
			// Clear local state regardless
			localStorage.removeItem("access_token");
			delete api.defaults.headers.common.Authorization;
			setUser(null);
			setIsAuthenticated(false);
		}
	};

	const value = {
		user,
		loading,
		isAuthenticated,
		authMode,
		login,
		signup,
		logout,
		checkAuth,
	};

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
