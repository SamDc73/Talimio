import { Loader2 } from "lucide-react"
import { Navigate } from "react-router-dom"

import { useAuth } from "@/hooks/useAuth"

function ProtectedRoute({ children }) {
	const { isAuthenticated, loading } = useAuth()

	// Show loading spinner while checking auth
	if (loading) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<div className="text-center">
					<Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-2" />

					<p className="text-sm text-muted-foreground">Checking authentication...</p>
				</div>
			</div>
		)
	}

	// Require authentication for protected routes (component usage implies protection)
	if (!isAuthenticated) {
		return <Navigate to="/auth" replace />
	}

	return children
}

export default ProtectedRoute
