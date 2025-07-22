import { NODE_TEMPLATES } from "./node-templates";

export class NodeGenerator {
	static generateNodes(sourceNode, count = 1, graphContext = null) {
		console.log("Generating mock nodes:", { sourceNode, count, graphContext }); // Add this

		const templates = Object.keys(NODE_TEMPLATES);
		const nodes = [];

		for (let i = 0; i < count; i++) {
			const templateKey =
				templates[Math.floor(Math.random() * templates.length)];
			const template = NODE_TEMPLATES[templateKey];

			const node = {
				id: `generated-${Date.now()}-${i}`,
				type: template.type,
				position: { x: 0, y: 0 },
				data: {
					...template.data,
					label: `${template.data.label} ${i + 1}`,
					description: NodeGenerator.generateDescription(
						sourceNode,
						template,
						i,
					),
					metadata: {
						...template.data.metadata,
						createdAt: new Date().toISOString(),
						generation: {
							sourceNodeId: sourceNode.id,
							prompt: `Generated from ${sourceNode.data.label}`,
							sequence: i + 1,
						},
					},
				},
			};

			console.log("Generated mock node:", node); // Add this
			nodes.push(node);
		}

		return nodes;
	}

	static generateDescription(sourceNode, template, index) {
		const descriptions = [
			`Generated from ${sourceNode.data.label}`,
			`A ${template.data.metadata.type} node created from the parent node`,
			`Expansion ${index + 1} of the ${sourceNode.data.label} node`,
			`Auto-generated ${template.data.metadata.type} node`,
		];

		return descriptions[Math.floor(Math.random() * descriptions.length)];
	}
}
