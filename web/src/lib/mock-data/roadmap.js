// frontend/src/lib/mock-data/roadmap.js
export const MOCK_ROADMAP_DATA = {
	nodes: [
		{
			id: "intro",
			type: "default",
			position: { x: 0, y: 0 },
			data: {
				label: "AI Engineer",
				description: "Introduction",
			},
		},
		{
			id: "llms",
			type: "default",
			position: { x: -200, y: 100 },
			data: {
				label: "LLMs",
				description: "Inference, Training, Embeddings",
			},
		},
		{
			id: "vector-db",
			type: "default",
			position: { x: 200, y: 100 },
			data: {
				label: "Vector Databases",
				description: "Understanding vector storage and retrieval",
			},
		},
		{
			id: "rag",
			type: "default",
			position: { x: 200, y: 200 },
			data: {
				label: "RAG",
				description: "Retrieval Augmented Generation",
			},
		},
		{
			id: "prompt-eng",
			type: "default",
			position: { x: -200, y: 200 },
			data: {
				label: "Prompt Engineering",
				description: "Mastering prompt design",
			},
		},
	],
	edges: [
		{
			id: "e1-2",
			source: "intro",
			target: "llms",
		},
		{
			id: "e1-3",
			source: "intro",
			target: "vector-db",
		},
		{
			id: "e2-5",
			source: "llms",
			target: "prompt-eng",
		},
		{
			id: "e3-4",
			source: "vector-db",
			target: "rag",
		},
	],
};
