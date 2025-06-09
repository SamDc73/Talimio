import { Loader2, Wand2 } from "lucide-react";
import React, { useState } from "react";

import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { useToast } from "@/hooks/use-toast";
import { ROADMAP_DEFAULTS } from "@/lib/constants";

export const NodeGenerationForm = ({ onGenerate }) => {
	const [count, setCount] = useState(1);
	const [isGenerating, setIsGenerating] = useState(false);
	const { toast } = useToast();

	const handleGenerate = async () => {
		try {
			setIsGenerating(true);
			await onGenerate(count);
			toast({
				title: "Success",
				description: `Generated ${count} new nodes.`,
			});
		} catch (error) {
			toast({
				title: "Error",
				description: "Failed to generate nodes.",
				variant: "destructive",
			});
		} finally {
			setIsGenerating(false);
		}
	};

	return (
		<div className="border rounded-lg p-4">
			<h4 className="text-sm font-medium leading-none mb-3">Generate Nodes</h4>
			<div className="flex items-center space-x-2">
				<Input
					type="number"
					min="1"
					max={ROADMAP_DEFAULTS.MAX_GENERATED_NODES}
					value={count}
					onChange={(e) => setCount(Number.parseInt(e.target.value) || 1)}
					className="w-20"
					disabled={isGenerating}
				/>
				<Button onClick={handleGenerate} disabled={isGenerating}>
					{isGenerating ? (
						<>
							<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							Generating
						</>
					) : (
						<>
							<Wand2 className="mr-2 h-4 w-4" />
							Generate
						</>
					)}
				</Button>
			</div>
		</div>
	);
};
