import { Loader2 } from "lucide-react"
import { Navigate } from "react-router-dom"

import { useAuth } from "@/hooks/useAuth"

function ProtectedRoute({ children, strict = false }) {
	const { isAuthenticated, loading, authMode } = useAuth()

	// Show loading spinner while checking auth
	if (loading) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<div className="text-center">
					<Loader2 className="w-8 h-8 animate-spin text-green-500 mx-auto mb-2" />
					<p className="text-sm text-gray-100-foreground">Checking authentication...</p>
				</div>
			</div>
		)
	}

	// In strict mode or when auth is enabled, require authentication
	const requiresAuth = strict || authMode === "supabase"

	if (requiresAuth && !isAuthenticated) {
		return <Navigate to="/auth" replace />
	}

	// In single-user mode (authMode === "none"), allow access even if isAuthenticated is false
	// This handles the case where auth is disabled but we still want protection
	if (authMode === "none") {
		return children
	}

	if (isAuthenticated) {
		return children
	}
	return <Navigate to="/auth" replace />
}

export default ProtectedRoute
