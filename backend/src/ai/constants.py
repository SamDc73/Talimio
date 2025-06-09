"""Constants for AI module configuration."""

# Tag categories for classification
TAG_CATEGORIES = {
    "language": ["python", "javascript", "java", "cpp", "go", "rust", "ruby", "php", "swift", "kotlin", "r", "matlab"],
    "framework": [
        "react",
        "angular",
        "vue",
        "django",
        "flask",
        "spring",
        "express",
        "rails",
        "laravel",
        "tensorflow",
        "pytorch",
    ],
    "domain": [
        "web-development",
        "machine-learning",
        "data-science",
        "mobile-development",
        "devops",
        "cloud-computing",
        "cybersecurity",
        "blockchain",
    ],
    "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra"],
    "tool": ["git", "docker", "kubernetes", "jenkins", "aws", "azure", "gcp", "linux", "bash"],
    "concept": [
        "algorithms",
        "data-structures",
        "testing",
        "deployment",
        "api-design",
        "microservices",
        "design-patterns",
    ],
}

# Default colors for tag categories (hex format)
TAG_CATEGORY_COLORS = {
    "language": "#3B82F6",  # Blue
    "framework": "#10B981",  # Green
    "domain": "#8B5CF6",  # Purple
    "database": "#F59E0B",  # Amber
    "tool": "#EF4444",  # Red
    "concept": "#6B7280",  # Gray
    "default": "#6366F1",  # Indigo
}
