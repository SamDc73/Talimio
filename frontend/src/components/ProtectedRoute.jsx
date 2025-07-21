import { Loader2 } from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

const ProtectedRoute = ({ children }) => {
	const { isAuthenticated, loading } = useAuth();

	// Show loading spinner while checking auth
	if (loading) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<Loader2 className="w-8 h-8 animate-spin text-primary" />
			</div>
		);
	}

	// Redirect to auth page if not authenticated
	if (!isAuthenticated) {
		return <Navigate to="/auth" replace />;
	}

	return children;
};

export default ProtectedRoute;
