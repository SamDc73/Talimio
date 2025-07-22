export const NODE_TEMPLATES = {
	default: {
		type: "default",
		data: {
			label: "Generated Node",
			description: "AI-generated node",
			metadata: {
				type: "generated",
				category: "auto",
			},
		},
	},
	task: {
		type: "task",
		data: {
			label: "Task Node",
			description: "A task to be completed",
			metadata: {
				type: "task",
				category: "workflow",
			},
		},
	},
	decision: {
		type: "decision",
		data: {
			label: "Decision Node",
			description: "A decision point in the flow",
			metadata: {
				type: "decision",
				category: "workflow",
			},
		},
	},
};
