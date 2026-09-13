import { Loader2 } from "lucide-react"
import { Navigate, useLocation } from "react-router-dom"

import { useAuth } from "@/hooks/use-auth"

function ProtectedRoute({ children }) {
	const { isAuthenticated, loading } = useAuth()
	const location = useLocation()

	// Show loading spinner while checking auth
	if (loading) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<div className="text-center">
					<Loader2 className="size-8  animate-spin text-primary mx-auto mb-2" />

					<p className="text-sm text-muted-foreground">Checking authentication...</p>
				</div>
			</div>
		)
	}

	// Require authentication for protected routes (component usage implies protection).
	// Send the learner back here after login so share links (/join/:token) survive the round trip.
	if (!isAuthenticated) {
		const redirect = encodeURIComponent(`${location.pathname}${location.search}`)
		return <Navigate to={`/auth?redirect=${redirect}`} replace />
	}

	return children
}

export default ProtectedRoute
