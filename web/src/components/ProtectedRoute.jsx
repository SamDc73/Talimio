import { Loader2 } from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

const ProtectedRoute = ({ children, strict = false }) => {
	const { isAuthenticated, loading, authMode } = useAuth();

	console.log("🛡️ ProtectedRoute check:", {
		isAuthenticated,
		loading,
		authMode,
		strict,
	});

	// Show loading spinner while checking auth
	if (loading) {
		console.log("⏳ Showing loading spinner...");
		return (
			<div className="min-h-screen flex items-center justify-center">
				<div className="text-center">
					<Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-2" />
					<p className="text-sm text-muted-foreground">
						Checking authentication...
					</p>
				</div>
			</div>
		);
	}

	// In strict mode or when auth is enabled, require authentication
	const requiresAuth = strict || authMode === "supabase";

	if (requiresAuth && !isAuthenticated) {
		console.log("🚫 User not authenticated, redirecting to /auth");
		return <Navigate to="/auth" replace />;
	}

	// In single-user mode (authMode === "none"), allow access even if isAuthenticated is false
	// This handles the case where auth is disabled but we still want protection
	if (authMode === "none") {
		console.log("🔓 Single-user mode: allowing access");
		return children;
	}

	if (isAuthenticated) {
		console.log("✅ User authenticated, rendering protected content");
		return children;
	}

	// Fallback: if we get here, something went wrong
	console.log("❌ Unexpected auth state, redirecting to /auth");
	return <Navigate to="/auth" replace />;
};

export default ProtectedRoute;
