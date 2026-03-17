import { LearningCapabilityToolCard } from "@/features/assistant/components/AssistantToolRegistry"
import { ToolFallback } from "@/features/assistant/components/ToolFallback"

const LEARNING_TOOL_NAMES = [
	"search_lessons",
	"list_relevant_courses",
	"get_course_state",
	"get_course_outline_state",
	"get_lesson_state",
	"get_course_frontier",
	"create_course",
	"append_course_lesson",
	"extend_lesson_with_context",
	"regenerate_lesson_with_context",
]

const TOOL_COMPONENTS_BY_NAME = Object.freeze(
	Object.fromEntries(LEARNING_TOOL_NAMES.map((toolName) => [toolName, LearningCapabilityToolCard]))
)

export function getAssistantToolRenderers() {
	return {
		Fallback: ToolFallback,
		by_name: TOOL_COMPONENTS_BY_NAME,
	}
}
