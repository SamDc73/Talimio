import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { RadioGroup, RadioGroupItem } from "@/components/radio-group";
import { toast } from "@/hooks/use-toast";
import { api } from "@/lib/apiClient";
import { AnimatePresence, motion } from "framer-motion";
import {
	ArrowLeft,
	BookOpen,
	Check,
	Edit2,
	Plus,
	RefreshCw,
	Save,
	Sparkles,
	Target,
	X,
	Zap,
} from "lucide-react";
import React, { useState, useEffect } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

const RoadmapPreviewPage = () => {
	const { roadmapId } = useParams();
	const navigate = useNavigate();
	const location = useLocation();
	const { isNew = false, originalPrompt = "" } = location.state || {};

	const [roadmap, setRoadmap] = useState(null);
	const [isLoading, setIsLoading] = useState(true);
	const [isSaving, setIsSaving] = useState(false);
	const [isRegenerating, setIsRegenerating] = useState(false);
	const [editingTitle, setEditingTitle] = useState(false);
	const [newTag, setNewTag] = useState("");

	// Form state
	const [formData, setFormData] = useState({
		title: "",
		description: "",
		skillLevel: "beginner",
		tags: [],
	});

	const skillLevels = [
		{
			value: "beginner",
			label: "Beginner",
			description: "New to this topic",
			icon: BookOpen,
			color: "bg-green-500",
		},
		{
			value: "intermediate",
			label: "Intermediate",
			description: "Some experience",
			icon: Target,
			color: "bg-yellow-500",
		},
		{
			value: "advanced",
			label: "Advanced",
			description: "Experienced learner",
			icon: Zap,
			color: "bg-red-500",
		},
	];

	// Load roadmap data
	useEffect(() => {
		const loadRoadmap = async () => {
			try {
				setIsLoading(true);
				const response = await api.get(`/roadmaps/${roadmapId}`);
				setRoadmap(response.data);

				// Parse tags from JSON string
				let tags = [];
				try {
					tags = response.data.tags_json
						? JSON.parse(response.data.tags_json)
						: [];
				} catch (e) {
					console.warn("Failed to parse tags:", e);
				}

				setFormData({
					title: response.data.title,
					description: response.data.description,
					skillLevel: response.data.skill_level,
					tags: tags,
				});
			} catch (error) {
				console.error("Error loading roadmap:", error);
				toast({
					title: "Error",
					description: "Failed to load roadmap.",
					variant: "destructive",
				});
				navigate("/");
			} finally {
				setIsLoading(false);
			}
		};

		if (roadmapId) {
			loadRoadmap();
		}
	}, [roadmapId, navigate]);

	const handleInputChange = (field, value) => {
		setFormData((prev) => ({
			...prev,
			[field]: value,
		}));
	};

	const addTag = () => {
		if (newTag.trim() && !formData.tags.includes(newTag.trim())) {
			setFormData((prev) => ({
				...prev,
				tags: [...prev.tags, newTag.trim()],
			}));
			setNewTag("");
		}
	};

	const removeTag = (tagToRemove) => {
		setFormData((prev) => ({
			...prev,
			tags: prev.tags.filter((tag) => tag !== tagToRemove),
		}));
	};

	const handleKeyPress = (e) => {
		if (e.key === "Enter") {
			e.preventDefault();
			addTag();
		}
	};

	const handleSave = async () => {
		if (!formData.title.trim()) {
			toast({
				title: "Title Required",
				description: "Please enter a title for your roadmap.",
				variant: "destructive",
			});
			return;
		}

		setIsSaving(true);

		try {
			await api.patch(`/roadmaps/${roadmapId}`, {
				title: formData.title,
				description: formData.description,
				skill_level: formData.skillLevel,
				tags: formData.tags,
			});

			toast({
				title: "Roadmap Updated!",
				description: "Your roadmap has been saved successfully.",
			});

			// Navigate to the roadmap view
			navigate(`/roadmap/${roadmapId}`);
		} catch (error) {
			console.error("Error updating roadmap:", error);
			toast({
				title: "Save Failed",
				description: "Failed to save roadmap. Please try again.",
				variant: "destructive",
			});
		} finally {
			setIsSaving(false);
		}
	};

	const handleRegenerate = async () => {
		if (!originalPrompt) {
			toast({
				title: "Cannot Regenerate",
				description: "No original prompt available for regeneration.",
				variant: "destructive",
			});
			return;
		}

		setIsRegenerating(true);

		try {
			// Delete current roadmap and create new one
			await api.delete(`/roadmaps/${roadmapId}`);

			const response = await api.post("/roadmaps", {
				title: originalPrompt,
				description: `Learning roadmap for: ${originalPrompt}`,
				skill_level: formData.skillLevel,
				tags: [],
			});

			toast({
				title: "Roadmap Regenerated!",
				description: "A new roadmap has been generated.",
			});

			// Navigate to new roadmap preview
			navigate(`/roadmap/preview/${response.data.id}`, {
				state: {
					isNew: true,
					originalPrompt: originalPrompt,
				},
				replace: true,
			});
		} catch (error) {
			console.error("Error regenerating roadmap:", error);
			toast({
				title: "Regeneration Failed",
				description: "Failed to regenerate roadmap. Please try again.",
				variant: "destructive",
			});
		} finally {
			setIsRegenerating(false);
		}
	};

	if (isLoading) {
		return (
			<div className="min-h-screen bg-background flex items-center justify-center">
				<div className="text-center">
					<div className="w-8 h-8 border-2 border-course border-t-transparent rounded-full animate-spin mx-auto mb-4" />
					<p className="text-muted-foreground">Loading roadmap...</p>
				</div>
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			{/* Header */}
			<div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
				<div className="max-w-4xl mx-auto px-6 py-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							<Button
								variant="ghost"
								size="sm"
								onClick={() => navigate("/")}
								className="gap-2"
							>
								<ArrowLeft className="h-4 w-4" />
								Back to Dashboard
							</Button>
							<div className="flex items-center gap-2">
								<div className="p-1 bg-gradient-to-br from-cyan-500 to-teal-500 rounded">
									<Sparkles className="h-4 w-4 text-white" />
								</div>
								<h1 className="text-lg font-semibold">
									{isNew ? "Review Your Roadmap" : "Edit Roadmap"}
								</h1>
							</div>
						</div>
						<div className="flex items-center gap-2">
							{isNew && originalPrompt && (
								<Button
									variant="outline"
									size="sm"
									onClick={handleRegenerate}
									disabled={isRegenerating}
									className="gap-2"
								>
									<RefreshCw
										className={`h-4 w-4 ${isRegenerating ? "animate-spin" : ""}`}
									/>
									Regenerate
								</Button>
							)}
							<Button
								onClick={handleSave}
								disabled={isSaving}
								className="gap-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white"
							>
								{isSaving ? (
									<>
										<div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
										Saving...
									</>
								) : (
									<>
										<Save className="h-4 w-4" />
										Save & Continue
									</>
								)}
							</Button>
						</div>
					</div>
				</div>
			</div>

			{/* Content */}
			<div className="max-w-4xl mx-auto px-6 py-8">
				<div className="grid gap-8 lg:grid-cols-3">
					{/* Main Form */}
					<div className="lg:col-span-2 space-y-6">
						{/* Title Section */}
						<div className="bg-white rounded-lg border p-6 space-y-4">
							<div className="flex items-center justify-between">
								<Label className="text-base font-medium">Roadmap Title</Label>
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setEditingTitle(!editingTitle)}
									className="gap-2"
								>
									{editingTitle ? (
										<Check className="h-4 w-4" />
									) : (
										<Edit2 className="h-4 w-4" />
									)}
									{editingTitle ? "Done" : "Edit"}
								</Button>
							</div>
							{editingTitle ? (
								<Input
									value={formData.title}
									onChange={(e) => handleInputChange("title", e.target.value)}
									placeholder="Enter roadmap title..."
									className="text-lg font-medium"
								/>
							) : (
								<h2 className="text-2xl font-bold text-foreground">
									{formData.title}
								</h2>
							)}
						</div>

						{/* Description */}
						<div className="bg-white rounded-lg border p-6 space-y-4">
							<Label className="text-base font-medium">Description</Label>
							<textarea
								value={formData.description}
								onChange={(e) =>
									handleInputChange("description", e.target.value)
								}
								placeholder="Describe your learning journey..."
								className="w-full min-h-[100px] px-3 py-2 text-sm border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring transition-all resize-none"
							/>
						</div>

						{/* Skill Level */}
						<div className="bg-white rounded-lg border p-6 space-y-4">
							<Label className="text-base font-medium">Skill Level</Label>
							<RadioGroup
								value={formData.skillLevel}
								onValueChange={(value) =>
									handleInputChange("skillLevel", value)
								}
								className="grid grid-cols-1 gap-3"
							>
								{skillLevels.map((level) => {
									const IconComponent = level.icon;
									return (
										<div key={level.value} className="relative">
											<RadioGroupItem
												value={level.value}
												id={level.value}
												className="peer sr-only"
											/>
											<Label
												htmlFor={level.value}
												className="flex items-center gap-3 p-3 rounded-md border-2 border-border cursor-pointer transition-all hover:border-course peer-checked:border-course peer-checked:bg-course/10"
											>
												<div
													className={`p-2 rounded-full ${level.color} text-white`}
												>
													<IconComponent className="h-4 w-4" />
												</div>
												<div className="flex-1">
													<div className="font-medium">{level.label}</div>
													<div className="text-sm text-muted-foreground">
														{level.description}
													</div>
												</div>
											</Label>
										</div>
									);
								})}
							</RadioGroup>
						</div>

						{/* Tags */}
						<div className="bg-white rounded-lg border p-6 space-y-4">
							<Label className="text-base font-medium">Tags</Label>
							<div className="flex gap-2">
								<Input
									placeholder="Add tags..."
									value={newTag}
									onChange={(e) => setNewTag(e.target.value)}
									onKeyPress={handleKeyPress}
									className="flex-1"
								/>
								<Button
									type="button"
									onClick={addTag}
									variant="outline"
									size="icon"
									disabled={!newTag.trim()}
								>
									<Plus className="h-4 w-4" />
								</Button>
							</div>

							{formData.tags.length > 0 && (
								<div className="flex flex-wrap gap-2">
									<AnimatePresence>
										{formData.tags.map((tag) => (
											<motion.div
												key={tag}
												initial={{ opacity: 0, scale: 0.8 }}
												animate={{ opacity: 1, scale: 1 }}
												exit={{ opacity: 0, scale: 0.8 }}
												className="flex items-center"
											>
												<Badge
													variant="secondary"
													className="flex items-center gap-1 pr-1 py-1"
												>
													{tag}
													<Button
														type="button"
														onClick={() => removeTag(tag)}
														variant="ghost"
														size="sm"
														className="h-4 w-4 p-0 hover:bg-destructive hover:text-destructive-foreground"
													>
														<X className="h-3 w-3" />
													</Button>
												</Badge>
											</motion.div>
										))}
									</AnimatePresence>
								</div>
							)}
						</div>
					</div>

					{/* Sidebar */}
					<div className="space-y-6">
						{/* Preview Card */}
						<div className="bg-white rounded-lg border p-6 space-y-4">
							<h3 className="font-medium flex items-center gap-2">
								<Sparkles className="h-4 w-4" />
								Preview
							</h3>
							<div className="space-y-3 text-sm">
								<div>
									<span className="font-medium">Title:</span>
									<p className="text-muted-foreground mt-1">
										{formData.title || "Untitled Roadmap"}
									</p>
								</div>
								<div>
									<span className="font-medium">Level:</span>
									<p className="text-muted-foreground mt-1 capitalize">
										{formData.skillLevel}
									</p>
								</div>
								<div>
									<span className="font-medium">Tags:</span>
									<div className="flex flex-wrap gap-1 mt-1">
										{formData.tags.length > 0 ? (
											formData.tags.map((tag) => (
												<Badge key={tag} variant="outline" className="text-xs">
													{tag}
												</Badge>
											))
										) : (
											<span className="text-muted-foreground text-xs">
												No tags
											</span>
										)}
									</div>
								</div>
							</div>
						</div>

						{/* Info */}
						{isNew && (
							<div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
								<div className="flex items-start gap-3">
									<Sparkles className="h-4 w-4 text-blue-500 mt-0.5" />
									<div className="text-sm">
										<p className="font-medium text-blue-900 dark:text-blue-100">
											AI Generated
										</p>
										<p className="text-blue-700 dark:text-blue-300 mt-1">
											This roadmap was generated based on your prompt. Feel free
											to edit the title, description, and tags before saving.
										</p>
									</div>
								</div>
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};

export default RoadmapPreviewPage;
