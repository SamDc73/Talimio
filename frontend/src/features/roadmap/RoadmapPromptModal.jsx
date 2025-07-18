import { motion } from "framer-motion";
import { Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/dialog";
import { toast } from "@/hooks/use-toast";
import { api } from "@/lib/apiClient";

const RoadmapPromptModal = ({ open, onOpenChange, onRoadmapCreated }) => {
	const [prompt, setPrompt] = useState("");
	const [isGenerating, setIsGenerating] = useState(false);
	const navigate = useNavigate();

	const handleSubmit = async (e) => {
		e.preventDefault();

		if (!prompt.trim()) {
			toast({
				title: "Prompt Required",
				description: "Please describe what you want to learn.",
				variant: "destructive",
			});
			return;
		}

		setIsGenerating(true);

		try {
			// Generate roadmap with AI using the prompt
			const response = await api.post("/courses/", {
				prompt: prompt.trim(),
			});

			toast({
				title: "Course Generated!",
				description: "Review and customize your learning course.",
			});

			// Navigate to course preview page for editing
			navigate(`/course/preview/${response.id}`, {
				state: {
					isNew: true,
					originalPrompt: prompt.trim(),
				},
			});

			if (onRoadmapCreated) {
				onRoadmapCreated(response);
			}
			onOpenChange(false);
			setPrompt("");
		} catch (error) {
			console.error("Error generating course:", error);
			toast({
				title: "Generation Failed",
				description: "Failed to generate course. Please try again.",
				variant: "destructive",
			});
		} finally {
			setIsGenerating(false);
		}
	};

	const handleClose = () => {
		if (!isGenerating) {
			setPrompt("");
			onOpenChange(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={handleClose}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader className="space-y-4">
					<DialogTitle className="flex items-center gap-3 text-2xl">
						<div className="p-2 bg-gradient-to-br from-cyan-500 to-teal-500 rounded-lg">
							<Wand2 className="h-6 w-6 text-white" />
						</div>
						Generate Learning Course
					</DialogTitle>
					<DialogDescription className="text-muted-foreground text-sm">
						Tell us what you want to learn, and AI will create a personalized
						course for you
					</DialogDescription>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="space-y-6">
					{/* Prompt Input */}
					<div className="space-y-3">
						<div className="relative">
							<textarea
								placeholder="What would you like to learn? (e.g., 'Learn React and build modern web apps', 'Master Python for data science', 'Get started with machine learning'...)"
								value={prompt}
								onChange={(e) => setPrompt(e.target.value)}
								className="w-full min-h-[120px] px-4 py-3 text-sm border border-input bg-background rounded-lg focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring transition-all resize-none placeholder:text-muted-foreground/60"
								disabled={isGenerating}
								maxLength={500}
							/>
							<div className="absolute bottom-3 right-3 text-xs text-muted-foreground">
								{prompt.length}/500
							</div>
						</div>

						{/* Example prompts */}
						<div className="space-y-2">
							<p className="text-xs text-muted-foreground font-medium">
								💡 Example prompts:
							</p>
							<div className="flex flex-wrap gap-2">
								{[
									"Learn React and build modern web apps",
									"Master Python for data science",
									"Get started with machine learning",
									"Learn JavaScript fundamentals",
								].map((example) => (
									<button
										key={example}
										type="button"
										onClick={() => setPrompt(example)}
										disabled={isGenerating}
										className="text-xs px-3 py-1 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all"
									>
										{example}
									</button>
								))}
							</div>
						</div>
					</div>

					{/* Action Buttons */}
					<div className="flex gap-3 pt-4">
						<Button
							type="button"
							variant="outline"
							onClick={handleClose}
							className="flex-1"
							disabled={isGenerating}
						>
							Cancel
						</Button>
						<Button
							type="submit"
							className="flex-1 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white"
							disabled={isGenerating || !prompt.trim()}
						>
							{isGenerating ? (
								<motion.div
									className="flex items-center gap-2"
									initial={{ opacity: 0 }}
									animate={{ opacity: 1 }}
								>
									<motion.div
										className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
										animate={{ rotate: 360 }}
										transition={{
											duration: 1,
											repeat: Number.POSITIVE_INFINITY,
											ease: "linear",
										}}
									/>
									Generating...
								</motion.div>
							) : (
								<div className="flex items-center gap-2">
									<Sparkles className="h-4 w-4" />
									Generate Course
								</div>
							)}
						</Button>
					</div>

					{/* Info note */}
					<div className="text-xs text-muted-foreground text-center p-3 bg-muted/50 rounded-lg">
						<Sparkles className="h-3 w-3 inline mr-1" />
						AI will generate a title, tags, and learning path. You'll be able to
						edit everything on the next page.
					</div>
				</form>
			</DialogContent>
		</Dialog>
	);
};

export default RoadmapPromptModal;
