/**
 * Production Security Configuration
 * Essential security settings for 100k+ user scale
 */

export const SECURITY_CONFIG = {
	// Token Management
	TOKEN_EXPIRY: 15 * 60 * 1000, // 15 minutes
	REFRESH_TOKEN_EXPIRY: 7 * 24 * 60 * 60 * 1000, // 7 days

	// Rate Limiting (client-side tracking)
	RATE_LIMITS: {
		LOGIN_ATTEMPTS: { max: 5, window: 15 * 60 * 1000 }, // 5 attempts per 15 min
		API_REQUESTS: { max: 100, window: 60 * 1000 }, // 100 requests per minute
	},

	// Security Headers (for development awareness)
	REQUIRED_HEADERS: [
		"X-Content-Type-Options",
		"X-Frame-Options",
		"X-XSS-Protection",
		"Strict-Transport-Security",
		"Content-Security-Policy",
	],

	// Validation Rules
	PASSWORD_RULES: {
		minLength: 12,
		requireUppercase: true,
		requireLowercase: true,
		requireNumbers: true,
		requireSymbols: true,
		maxAttempts: 3,
	},
};

/**
 * Client-side security monitoring
 * Reports suspicious activity for server-side handling
 */
class SecurityMonitor {
	constructor() {
		this.attempts = new Map();
		this.violations = [];
	}

	// Track login attempts
	trackLoginAttempt(email, success) {
		const key = `login:${email}`;
		const attempts = this.attempts.get(key) || [];

		attempts.push({
			timestamp: Date.now(),
			success,
			ip: "client", // Server should track real IP
		});

		// Keep only recent attempts
		const cutoff =
			Date.now() - SECURITY_CONFIG.RATE_LIMITS.LOGIN_ATTEMPTS.window;
		const recentAttempts = attempts.filter((a) => a.timestamp > cutoff);

		this.attempts.set(key, recentAttempts);

		// Check for violations
		const failedAttempts = recentAttempts.filter((a) => !a.success);
		if (
			failedAttempts.length >= SECURITY_CONFIG.RATE_LIMITS.LOGIN_ATTEMPTS.max
		) {
			this.reportViolation("RATE_LIMIT_EXCEEDED", {
				email,
				attempts: failedAttempts.length,
			});
			return false; // Block attempt
		}

		return true; // Allow attempt
	}

	// Track API request rate
	trackApiRequest(endpoint) {
		const key = `api:${endpoint}`;
		const requests = this.attempts.get(key) || [];

		requests.push({ timestamp: Date.now() });

		// Keep only recent requests
		const cutoff = Date.now() - SECURITY_CONFIG.RATE_LIMITS.API_REQUESTS.window;
		const recentRequests = requests.filter((r) => r.timestamp > cutoff);

		this.attempts.set(key, recentRequests);

		// Check rate limit
		if (recentRequests.length > SECURITY_CONFIG.RATE_LIMITS.API_REQUESTS.max) {
			this.reportViolation("API_RATE_LIMIT", {
				endpoint,
				count: recentRequests.length,
			});
			return false;
		}

		return true;
	}

	// Report security violations
	reportViolation(type, details) {
		const violation = {
			type,
			details,
			timestamp: Date.now(),
			userAgent: navigator.userAgent,
			url: window.location.href,
		};

		this.violations.push(violation);

		// Log locally (server should handle real reporting)
		console.warn("🚨 Security violation detected:", violation);

		// In production, send to security monitoring service
		if (import.meta.env.PROD) {
			this.sendToSecurityService(violation);
		}
	}

	// Send to security monitoring service
	async sendToSecurityService(violation) {
		try {
			await fetch("/api/v1/security/violation", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(violation),
			});
		} catch (error) {
			console.error("Failed to report security violation:", error);
		}
	}

	// Validate password strength
	validatePassword(password) {
		const rules = SECURITY_CONFIG.PASSWORD_RULES;
		const issues = [];

		if (password.length < rules.minLength) {
			issues.push(`Must be at least ${rules.minLength} characters`);
		}

		if (rules.requireUppercase && !/[A-Z]/.test(password)) {
			issues.push("Must contain uppercase letters");
		}

		if (rules.requireLowercase && !/[a-z]/.test(password)) {
			issues.push("Must contain lowercase letters");
		}

		if (rules.requireNumbers && !/\d/.test(password)) {
			issues.push("Must contain numbers");
		}

		if (rules.requireSymbols && !/[^A-Za-z0-9]/.test(password)) {
			issues.push("Must contain special characters");
		}

		return {
			valid: issues.length === 0,
			issues,
			strength: this.calculatePasswordStrength(password),
		};
	}

	calculatePasswordStrength(password) {
		let score = 0;

		// Length bonus
		score += Math.min(password.length * 2, 20);

		// Character variety
		if (/[a-z]/.test(password)) score += 5;
		if (/[A-Z]/.test(password)) score += 5;
		if (/\d/.test(password)) score += 5;
		if (/[^A-Za-z0-9]/.test(password)) score += 10;

		// Pattern penalties
		if (/(.)\1{2,}/.test(password)) score -= 10; // Repeated characters
		if (/123|abc|qwe/i.test(password)) score -= 15; // Common patterns

		if (score < 30) return "weak";
		if (score < 60) return "medium";
		if (score < 80) return "strong";
		return "very-strong";
	}

	// Check for common security headers
	checkSecurityHeaders() {
		const missing = [];

		// Note: This is limited in browser context
		// Real header checking should be done server-side
		SECURITY_CONFIG.REQUIRED_HEADERS.forEach((header) => {
			// Can only check some headers via meta tags or CSP reports
			if (header === "Content-Security-Policy") {
				const csp = document.querySelector(
					'meta[http-equiv="Content-Security-Policy"]',
				);
				if (!csp) missing.push(header);
			}
		});

		if (missing.length > 0) {
			this.reportViolation("MISSING_SECURITY_HEADERS", { missing });
		}

		return missing;
	}
}

// Global security monitor instance
export const securityMonitor = new SecurityMonitor();

// Auto-run security checks in production
if (import.meta.env.PROD) {
	// Check security headers on load
	window.addEventListener("load", () => {
		securityMonitor.checkSecurityHeaders();
	});
}
