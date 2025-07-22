export const MOCK_ONBOARDING_DATA = {
	questions: [
		{
			id: "name",
			title: "Welcome! What's your name?",
			type: "text",
			placeholder: "Enter your name",
		},
		{
			id: "role",
			title: "What best describes your role?",
			type: "select",
			options: [
				"Developer",
				"Designer",
				"Product Manager",
				"Business Analyst",
				"Other",
			],
		},
		{
			id: "useCase",
			title: "How do you plan to use this tool?",
			type: "select",
			options: [
				"Process Mapping",
				"System Architecture",
				"Workflow Design",
				"Organization Charts",
				"Other",
			],
		},
	],
	defaultAnswers: {
		name: "Guest User",
		role: "Developer",
		useCase: "Process Mapping",
	},
};
