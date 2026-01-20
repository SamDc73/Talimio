import { useEffect, useState } from "react"
import { useWorkspaceRegistry } from "@/features/course/hooks/use-workspace-registry"
import { flattenText, getLanguage } from "@/features/course/utils/codeBlockUtils"
import ExecutableCodeBlock from "./ExecutableCodeBlock.jsx"
import WorkspaceCodeRunner from "./WorkspaceCodeRunner.jsx"

function formatLabel(id) {
	if (!id) return "Workspace"
	const label = id.replaceAll("/", " ").replaceAll("_", " ").replaceAll("-", " ").trim()
	if (!label) return "Workspace"
	return label.charAt(0).toUpperCase() + label.slice(1)
}

export default function WorkspaceAwareCodeBlock({ lessonId, courseId, children, file, workspace, entry, ...props }) {
	const { registerBlock } = useWorkspaceRegistry()
	const filePath = file || null
	const workspaceId = workspace || filePath
	const isEntry = Boolean(entry)
	const code = flattenText(children)
	const language = getLanguage(props, children)

	const [shouldRenderRunner, setShouldRenderRunner] = useState(false)

	// Register block in effect to avoid state updates during render
	useEffect(() => {
		if (!filePath) return
		const registration = registerBlock({
			workspaceId,
			workspaceLabel: formatLabel(workspaceId),
			filePath,
			code,
			language,
			isEntry,
		})
		setShouldRenderRunner(registration.shouldRenderRunner)
	}, [registerBlock, workspaceId, filePath, code, language, isEntry])

	// Not a workspace block - render as regular executable code
	if (!filePath) {
		return (
			<ExecutableCodeBlock lessonId={lessonId} courseId={courseId} {...props}>
				{children}
			</ExecutableCodeBlock>
		)
	}

	if (!shouldRenderRunner) {
		return null
	}

	return <WorkspaceCodeRunner workspaceId={workspaceId} lessonId={lessonId} courseId={courseId} />
}
