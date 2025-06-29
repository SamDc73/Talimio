/**
 * Personalization Dialog Component for AI customization
 */

import { Brain, ChevronLeft, Eye, RotateCcw, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "../hooks/use-toast";
import {
	clearUserMemory,
	getUserMemories,
	getUserSettings,
	updateCustomInstructions,
} from "../services/personalizationApi";
import { Button } from "./button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "./dialog";
import { Label } from "./label";

export function PersonalizationDialog({ open, onOpenChange }) {
	const [isLoading, setIsLoading] = useState(false);
	const [isSaving, setIsSaving] = useState(false);
	const [isClearing, setIsClearing] = useState(false);
	const [instructions, setInstructions] = useState("");
	const [memoryCount, setMemoryCount] = useState(0);
	const [hasChanges, setHasChanges] = useState(false);
	const [originalInstructions, setOriginalInstructions] = useState("");
	const [showMemories, setShowMemories] = useState(false);
	const [memories, setMemories] = useState([]);
	const [isLoadingMemories, setIsLoadingMemories] = useState(false);

	const loadUserSettings = useCallback(async () => {
		setIsLoading(true);
		try {
			const settings = await getUserSettings();
			setInstructions(settings.custom_instructions || "");
			setOriginalInstructions(settings.custom_instructions || "");
			setMemoryCount(settings.memory_count || 0);
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to load personalization settings",
				variant: "destructive",
			});
		} finally {
			setIsLoading(false);
		}
	}, []);

	// Load user settings when dialog opens
	useEffect(() => {
		if (open) {
			loadUserSettings();
		}
	}, [open, loadUserSettings]);

	// Track changes
	useEffect(() => {
		setHasChanges(instructions !== originalInstructions);
	}, [instructions, originalInstructions]);

	const handleSave = async () => {
		setIsSaving(true);
		try {
			await updateCustomInstructions(instructions);
			setOriginalInstructions(instructions);
			toast({
				title: "Success",
				description: "Your AI personalization has been saved",
			});
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to save personalization settings",
				variant: "destructive",
			});
		} finally {
			setIsSaving(false);
		}
	};

	const handleClearMemory = async () => {
		if (
			!window.confirm(
				"Are you sure you want to clear all your learning history? This action cannot be undone.",
			)
		) {
			return;
		}

		setIsClearing(true);
		try {
			await clearUserMemory();
			setMemoryCount(0);
			toast({
				title: "Success",
				description: "Your learning history has been cleared",
			});
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to clear learning history",
				variant: "destructive",
			});
		} finally {
			setIsClearing(false);
		}
	};

	const handleReset = () => {
		setInstructions(originalInstructions);
	};

	const handleViewMemories = async () => {
		if (showMemories) {
			setShowMemories(false);
			return;
		}

		setIsLoadingMemories(true);
		try {
			const userMemories = await getUserMemories();
			setMemories(userMemories);
			setShowMemories(true);
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to load memories",
				variant: "destructive",
			});
		} finally {
			setIsLoadingMemories(false);
		}
	};

	const formatTimestamp = (timestamp) => {
		if (!timestamp) return "Unknown time";
		try {
			const date = new Date(timestamp);
			return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
				hour: "2-digit",
				minute: "2-digit",
			})}`;
		} catch {
			return timestamp;
		}
	};

	const characterCount = instructions.length;
	const maxCharacters = 1500;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						{showMemories && (
							<Button
								variant="ghost"
								size="sm"
								onClick={() => setShowMemories(false)}
								className="p-1 h-8 w-8"
							>
								<ChevronLeft className="h-4 w-4" />
							</Button>
						)}
						<Brain className="h-5 w-5 text-primary" />
						{showMemories ? "Your Learning Memories" : "Personalize Talimio"}
					</DialogTitle>
					<DialogDescription>
						{showMemories
							? "Review your stored learning interactions and preferences"
							: "Customize how AI responds to you based on your learning preferences and history."}
					</DialogDescription>
				</DialogHeader>

				{isLoading ? (
					<div className="flex items-center justify-center py-8">
						<div className="text-sm text-muted-foreground">
							Loading settings...
						</div>
					</div>
				) : showMemories ? (
					<div className="space-y-4">
						{isLoadingMemories ? (
							<div className="flex items-center justify-center py-8">
								<div className="text-sm text-muted-foreground">
									Loading memories...
								</div>
							</div>
						) : memories.length === 0 ? (
							<div className="text-center py-8">
								<div className="text-sm text-muted-foreground">
									No memories found
								</div>
							</div>
						) : (
							<div className="space-y-3 max-h-[400px] overflow-y-auto">
								{memories.map((memory, index) => (
									<div
										key={index}
										className="bg-muted/30 p-3 rounded-lg border-l-2 border-primary/20"
									>
										<p className="text-sm font-medium text-foreground mb-2">
											{memory.content}
										</p>
										<div className="flex items-center justify-between text-xs text-muted-foreground">
											<span>{formatTimestamp(memory.timestamp)}</span>
											<span className="bg-muted px-2 py-1 rounded text-xs">
												{memory.source}
											</span>
										</div>
										{memory.metadata &&
											Object.keys(memory.metadata).length > 0 && (
												<div className="mt-2 flex flex-wrap gap-1">
													{Object.entries(memory.metadata)
														.filter(
															([key, value]) =>
																key !== "timestamp" &&
																key !== "source" &&
																value &&
																value !== "now",
														)
														.map(([key, value]) => (
															<span
																key={key}
																className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded"
															>
																{key}: {value}
															</span>
														))}
												</div>
											)}
									</div>
								))}
							</div>
						)}

						<div className="flex justify-between pt-4">
							<Button variant="outline" onClick={() => setShowMemories(false)}>
								<ChevronLeft className="h-4 w-4 mr-2" />
								Back to Settings
							</Button>
							<Button variant="outline" onClick={() => onOpenChange(false)}>
								Close
							</Button>
						</div>
					</div>
				) : (
					<div className="space-y-6">
						{/* Custom Instructions Section */}
						<div className="space-y-3">
							<Label htmlFor="instructions" className="text-sm font-medium">
								Custom Instructions
							</Label>
							<div className="space-y-2">
								<textarea
									id="instructions"
									value={instructions}
									onChange={(e) => setInstructions(e.target.value)}
									placeholder="Tell the AI how you'd like it to respond. For example: 'I prefer concise explanations with practical examples' or 'I'm a visual learner who likes diagrams and step-by-step guides.'"
									className="w-full min-h-[120px] p-3 text-sm border border-input bg-background rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
									maxLength={maxCharacters}
								/>
								<div className="flex justify-between items-center text-xs text-muted-foreground">
									<span>
										These instructions will be included in all AI interactions
									</span>
									<span
										className={
											characterCount > maxCharacters * 0.9 ? "text-warning" : ""
										}
									>
										{characterCount}/{maxCharacters}
									</span>
								</div>
							</div>
						</div>

						{/* Memory Statistics */}
						<div className="space-y-3">
							<Label className="text-sm font-medium">Learning History</Label>
							<div className="bg-muted/50 p-4 rounded-lg">
								<div className="flex items-center justify-between">
									<div className="flex-1">
										<button
											onClick={handleViewMemories}
											disabled={memoryCount === 0 || isLoadingMemories}
											className="text-left group disabled:cursor-not-allowed"
										>
											<p className="text-sm font-medium group-hover:text-primary group-disabled:text-muted-foreground transition-colors">
												{memoryCount} memories stored
											</p>
											<p className="text-xs text-muted-foreground">
												{memoryCount > 0
													? "Click to view your stored learning interactions"
													: "AI learns from your interactions to provide personalized responses"}
											</p>
										</button>
									</div>
									<div className="flex gap-2">
										{memoryCount > 0 && (
											<Button
												variant="outline"
												size="sm"
												onClick={handleViewMemories}
												disabled={isLoadingMemories}
											>
												<Eye className="h-4 w-4 mr-2" />
												{isLoadingMemories ? "Loading..." : "View"}
											</Button>
										)}
										<Button
											variant="outline"
											size="sm"
											onClick={handleClearMemory}
											disabled={isClearing || memoryCount === 0}
											className="text-destructive hover:text-destructive"
										>
											<Trash2 className="h-4 w-4 mr-2" />
											{isClearing ? "Clearing..." : "Clear All"}
										</Button>
									</div>
								</div>
							</div>
						</div>

						{/* Action Buttons */}
						<div className="flex justify-between pt-4">
							<Button
								variant="outline"
								onClick={handleReset}
								disabled={!hasChanges || isSaving}
							>
								<RotateCcw className="h-4 w-4 mr-2" />
								Reset
							</Button>
							<div className="flex gap-2">
								<Button
									variant="outline"
									onClick={() => onOpenChange(false)}
									disabled={isSaving}
								>
									Cancel
								</Button>
								<Button onClick={handleSave} disabled={!hasChanges || isSaving}>
									<Save className="h-4 w-4 mr-2" />
									{isSaving ? "Saving..." : "Save Changes"}
								</Button>
							</div>
						</div>
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
