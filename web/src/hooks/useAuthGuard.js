import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

/**
 * Authentication guard hook that enforces auth requirements
 * Usage: const { user, isAuthenticated } = useAuthGuard();
 */
export const useAuthGuard = (redirectPath = "/auth") => {
	const { isAuthenticated, loading, user, authMode } = useAuth();
	const navigate = useNavigate();

	useEffect(() => {
		// Don't redirect while still loading
		if (loading) return;

		// If auth is enabled and user is not authenticated, redirect
		if (authMode !== "none" && !isAuthenticated) {
			console.log(
				"🚨 useAuthGuard: Unauthorized access attempt, redirecting to",
				redirectPath,
			);
			navigate(redirectPath, { replace: true });
		}
	}, [isAuthenticated, loading, authMode, navigate, redirectPath]);

	return {
		isAuthenticated,
		loading,
		user,
		authMode,
		isAllowed: loading || isAuthenticated || authMode === "none",
	};
};

/**
 * Component-level auth guard that prevents rendering if not authenticated
 */
export const useStrictAuthGuard = () => {
	const { isAuthenticated, loading, user, authMode } = useAuth();

	// In strict mode, never allow unauthenticated access (even in single-user mode)
	const isAllowed = isAuthenticated && !loading;

	if (!isAllowed && !loading) {
		console.log("🚨 useStrictAuthGuard: Strict auth violation detected");
	}

	return {
		isAuthenticated,
		loading,
		user,
		authMode,
		isAllowed,
	};
};
