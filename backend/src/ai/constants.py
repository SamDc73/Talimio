"""Constants for AI module including prompts and configuration."""

CONTENT_TAGGING_PROMPT = """
Analyze the following {content_type} content and generate 3-7 relevant subject-based tags.

Title: {title}
Content Preview: {content_preview}

Guidelines:
- Use lowercase, hyphenated format (e.g., "machine-learning", "web-development", "python")
- Focus on technical subjects, programming languages, frameworks, domains, and methodologies
- Be specific but not overly narrow (prefer "react" over "react-hooks")
- Avoid generic terms like "programming", "technology", "tutorial"
- Consider the skill level and depth of content
- Include both broad categories and specific technologies when relevant

Examples of good tags:
- Programming languages: "python", "javascript", "rust", "go"
- Frameworks/Libraries: "react", "django", "tensorflow", "express"
- Domains: "machine-learning", "web-development", "data-science", "cybersecurity"
- Concepts: "algorithms", "databases", "testing", "deployment"

Return only a JSON array of tags: ["tag1", "tag2", "tag3", "tag4"]
"""

CONTENT_TAGGING_WITH_CONFIDENCE_PROMPT = """
Analyze the following {content_type} content and generate 3-7 relevant subject-based tags with confidence scores.

Title: {title}
Content Preview: {content_preview}

Guidelines:
- Use lowercase, hyphenated format (e.g., "machine-learning", "web-development", "python")
- Focus on technical subjects, programming languages, frameworks, domains, and methodologies
- Be specific but not overly narrow (prefer "react" over "react-hooks")
- Avoid generic terms like "programming", "technology", "tutorial"
- Consider the skill level and depth of content
- Include both broad categories and specific technologies when relevant
- Assign confidence scores between 0.0 and 1.0 based on relevance

Examples of good tags:
- Programming languages: "python", "javascript", "rust", "go"
- Frameworks/Libraries: "react", "django", "tensorflow", "express"
- Domains: "machine-learning", "web-development", "data-science", "cybersecurity"
- Concepts: "algorithms", "databases", "testing", "deployment"

Return only a JSON array of objects with tag and confidence:
[
    {{"tag": "python", "confidence": 0.95}},
    {{"tag": "machine-learning", "confidence": 0.85}},
    {{"tag": "tensorflow", "confidence": 0.75}}
]
"""

# Tag categories for classification
TAG_CATEGORIES = {
    "language": ["python", "javascript", "java", "cpp", "go", "rust", "ruby", "php", "swift", "kotlin", "r", "matlab"],
    "framework": ["react", "angular", "vue", "django", "flask", "spring", "express", "rails", "laravel", "tensorflow", "pytorch"],
    "domain": ["web-development", "machine-learning", "data-science", "mobile-development", "devops", "cloud-computing", "cybersecurity", "blockchain"],
    "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra"],
    "tool": ["git", "docker", "kubernetes", "jenkins", "aws", "azure", "gcp", "linux", "bash"],
    "concept": ["algorithms", "data-structures", "testing", "deployment", "api-design", "microservices", "design-patterns"],
}

# Default colors for tag categories (hex format)
TAG_CATEGORY_COLORS = {
    "language": "#3B82F6",  # Blue
    "framework": "#10B981",  # Green
    "domain": "#8B5CF6",    # Purple
    "database": "#F59E0B",  # Amber
    "tool": "#EF4444",      # Red
    "concept": "#6B7280",   # Gray
    "default": "#6366F1",   # Indigo
}
