import { useEffect, useState } from "react"

import { normalizePasswordPolicy } from "@/features/auth/passwordPolicy"
import { api } from "@/lib/apiClient"
import logger from "@/lib/logger"

const normalizeAuthOptions = (authOptions) => {
	if (!authOptions || typeof authOptions !== "object") {
		return null
	}

	return {
		...authOptions,
		passwordPolicy: normalizePasswordPolicy(authOptions.passwordPolicy),
	}
}

export const useAuthOptions = () => {
	const [authOptions, setAuthOptions] = useState(null)

	useEffect(() => {
		let isMounted = true

		const loadAuthOptions = async () => {
			try {
				const options = await api.get("/auth/options")
				if (!isMounted) {
					return
				}
				setAuthOptions(normalizeAuthOptions(options))
			} catch (error) {
				logger.error("Failed to load auth options; continuing with backend validation only", error)
			}
		}

		loadAuthOptions()

		return () => {
			isMounted = false
		}
	}, [])

	return { authOptions }
}
