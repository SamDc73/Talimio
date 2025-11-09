import { useCallback, useMemo } from "react"
import { shallow } from "zustand/shallow"
import useAppStore from "@/stores/useAppStore"

const selectCoursePreferences = (state) => ({
	focusMode: Boolean(state.preferences?.courseFocusMode),
	timeboxMinutes: state.preferences?.courseTimeboxMinutes,
	updatePreference: state.updatePreference,
})

export function useCoursePreferences() {
	const { focusMode, timeboxMinutes, updatePreference } = useAppStore(selectCoursePreferences, shallow)

	const normalizedTimebox = useMemo(() => {
		if (typeof timeboxMinutes === "number" && Number.isFinite(timeboxMinutes) && timeboxMinutes > 0) {
			return Math.round(timeboxMinutes)
		}
		return 10
	}, [timeboxMinutes])

	const setFocusMode = useCallback(
		(nextValue) => {
			updatePreference("courseFocusMode", Boolean(nextValue))
		},
		[updatePreference]
	)

	const setTimeboxMinutes = useCallback(
		(value) => {
			const normalized = typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.round(value) : 10
			updatePreference("courseTimeboxMinutes", normalized)
		},
		[updatePreference]
	)

	return useMemo(
		() => ({
			focusMode,
			timeboxMinutes: normalizedTimebox,
			setFocusMode,
			setTimeboxMinutes,
		}),
		[focusMode, normalizedTimebox, setFocusMode, setTimeboxMinutes]
	)
}
