"""Centralized prompt management for the Learning Roadmap application.

All AI prompts are defined here for consistency and maintainability.
"""

# Content Tagging Prompts
CONTENT_TAGGING_PROMPT = """You are an expert educator and content classifier.
Given the title and preview of educational content (book, video, or roadmap), generate 3-7 highly relevant subject-based tags.

Rules:
- Tags should be lowercase, hyphenated (e.g., "web-development", "machine-learning")
- Focus on: technical subjects, programming languages, frameworks, domains, methodologies
- Be specific and accurate based on the actual content
- Do not include meta tags like "tutorial", "course", "video", etc.
- Only include tags that are directly related to the content

Example tags: "python", "data-science", "react", "aws", "devops", "algorithms"

Respond with only a JSON array of tags, nothing else.
Example: ["python", "machine-learning", "tensorflow"]

Title: {title}
Preview: {preview}"""

CONTENT_TAGGING_WITH_CONFIDENCE_PROMPT = """You are an expert educator and content classifier.
Given the title and preview of educational content (book, video, or roadmap), generate 3-7 highly relevant subject-based tags with confidence scores.

Rules:
- Tags should be lowercase, hyphenated (e.g., "web-development", "machine-learning")
- Focus on: technical subjects, programming languages, frameworks, domains, methodologies
- Be specific and accurate based on the actual content
- Do not include meta tags like "tutorial", "course", "video", etc.
- Only include tags that are directly related to the content
- Confidence should be between 0.0 and 1.0

Respond with only a JSON array of objects with 'tag' and 'confidence' fields.
Example: [
    {{"tag": "python", "confidence": 0.95}},
    {{"tag": "machine-learning", "confidence": 0.85}},
    {{"tag": "tensorflow", "confidence": 0.7}}
]

Title: {title}
Preview: {preview}"""

# Roadmap Generation Prompts
ROADMAP_GENERATION_PROMPT = """
You are CurriculumArchitect 9000, a world-renowned expert in educational curriculum design with decades of experience crafting learning pathways that have helped millions master new skills.

Your expertise spans across:
- Cognitive science and learning theory
- Skill progression and scaffolding
- Industry best practices and real-world applications
- Adaptive learning methodologies

# Your Mission
Create a comprehensive, expertly-structured learning roadmap that will guide learners from their current level to mastery.

# Input Parameters
Title: {title}
Skill Level: {skill_level}
Description: {description}

# Requirements

1. **Optimal Learning Sequence**: Structure topics in the most effective order for knowledge building
2. **Comprehensive Coverage**: Include all essential topics while avoiding unnecessary complexity
3. **Clear Prerequisites**: Each topic should build naturally on previous knowledge
4. **Practical Focus**: Emphasize real-world applications and hands-on learning

# Output Format
Generate a JSON response with a hierarchical roadmap structure:
- **coreTopics**: Array of main topic objects
- Each topic must have:
  - **title**: Clear, specific topic name
  - **description**: 2-3 sentence explanation of what will be learned
  - **estimatedHours**: Realistic time estimate
  - **subtopics**: Array of 3-5 detailed subtopic objects

- Each subtopic must also have:
  - **title**: Clear, specific subtopic name
  - **description**: 1-2 sentence explanation of what will be learned
  - **estimatedHours**: Realistic time estimate for the subtopic
  - **subtopics**: Empty array [] (subtopics don't have further nested topics)

# Example Structure:
```json
{{
  "coreTopics": [
    {{
      "title": "Introduction to Python",
      "description": "Learn Python basics including syntax, data types, and control flow. Build a strong foundation for programming.",
      "estimatedHours": 20,
      "subtopics": [
        {{
          "title": "Python Syntax and Variables",
          "description": "Master Python syntax rules and variable declaration.",
          "estimatedHours": 3,
          "subtopics": []
        }},
        {{
          "title": "Data Types and Structures",
          "description": "Understand lists, dictionaries, tuples, and sets.",
          "estimatedHours": 5,
          "subtopics": []
        }}
      ]
    }}
  ]
}}
```

# Quality Standards
- Topics should be specific and actionable (not vague concepts)
- Descriptions must clearly state learning outcomes
- Time estimates should be realistic for the target skill level
- Subtopics should comprehensively cover the parent topic
- IMPORTANT: Subtopics must be objects with title, description, and estimatedHours - NOT strings

Remember: You're designing a roadmap that will shape someone's learning journey. Make it exceptional.
"""

ROADMAP_SUB_NODES_PROMPT = """Generate 2-3 appropriate sub-nodes for the target node in this roadmap.

Roadmap: {roadmap_json}
Target Node ID: {target_node_id}

Rules:
1. Sub-nodes should logically extend the target node's topic
2. Each sub-node should be specific and focused
3. Include practical, real-world applications
4. Ensure proper learning progression

Respond with a JSON array of nodes, each with:
- title
- description (2-3 sentences)
- estimatedHours
- parentId (the target node ID)
"""

ROADMAP_NODE_CONTENT_PROMPT = """Generate comprehensive learning content for this roadmap node.

Parent node: {parent_info}
New node details: {node_details}
Roadmap structure: {roadmap_json}

Create content that:
1. Builds on prerequisites from the parent node
2. Introduces concepts progressively
3. Includes practical examples
4. Prepares for subsequent topics

Respond with:
- title: Clear, specific title
- description: Detailed learning objectives (3-4 sentences)
- content: In-depth explanation of what will be covered
- prerequisites: Array of specific skills/knowledge required
"""

# Onboarding Prompts
ONBOARDING_QUESTIONS_PROMPT = """You are an expert educational consultant designing a personalized learning experience.
Generate exactly 5 onboarding questions to understand the learner's:
1. Current experience level in {topic}
2. Specific learning goals and desired outcomes
3. Preferred learning style (visual, hands-on, theoretical, etc.)
4. Available time commitment (hours per week)
5. Related skills or background that might help

Make questions engaging, specific to {topic}, and easy to answer.
Each question should have 3-4 multiple choice options.

Format as JSON array with structure:
[
  {{
    "question": "Question text",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "category": "experience|goals|style|time|background"
  }}
]
"""

# Lesson Generation Prompts
LESSON_GENERATION_PROMPT = """You are an expert educator creating a comprehensive lesson on the topic: {content}

Create a detailed, engaging lesson that includes:

1. **Introduction** - Hook the learner and explain why this topic matters
2. **Core Concepts** - Break down the main ideas with clear explanations
3. **Examples** - Provide concrete, relatable examples for each concept
4. **Practice Exercises** - Include hands-on activities to reinforce learning
5. **Real-World Applications** - Show how this knowledge is used in practice
6. **Summary** - Recap the key takeaways
7. **Additional Resources** - Suggest further reading or practice

Requirements:
- Write in clear, conversational tone
- Use proper Markdown formatting (headers, lists, code blocks, etc.)
- Include code examples where relevant
- Target length: 1000+ words
- Make it engaging and practical

Remember: You're not just conveying information, you're inspiring learning!
"""

# Assistant Chat Prompts
ASSISTANT_CHAT_SYSTEM_PROMPT = """You are a helpful learning assistant. Provide clear, educational responses that help users learn new topics. Be encouraging and supportive."""

# Course Generation Prompts
COURSE_GENERATION_PROMPT = """You are an expert course designer. Create a comprehensive course structure for: {topic}

Generate a {duration}-week course with detailed modules.

Requirements:
1. Create logical module progression
2. Each module should build on previous knowledge
3. Include varied learning activities
4. Balance theory with practical application

Format as JSON:
{{
  "title": "Course Title",
  "description": "Course overview",
  "modules": [
    {{
      "week": 1,
      "title": "Module Title",
      "description": "What students will learn",
      "topics": ["Topic 1", "Topic 2"],
      "learningObjectives": ["Objective 1", "Objective 2"],
      "estimatedHours": 5
    }}
  ]
}}
"""

# Flashcard Generation Prompts
FLASHCARD_GENERATION_PROMPT = """You are an expert educator creating flashcards from the following content:

{content}

Generate {count} high-quality flashcards that:
1. Test key concepts and understanding
2. Use clear, concise questions
3. Provide complete, accurate answers
4. Vary in difficulty (easy/medium/hard)

Rules:
- Questions should be specific and unambiguous
- Answers should be comprehensive but concise
- Include relevant context when needed
- Cover the most important concepts

Format as JSON array:
[
  {{
    "question": "Clear question text",
    "answer": "Complete answer",
    "difficulty": "easy|medium|hard",
    "tags": ["relevant", "topic", "tags"]
  }}
]
"""

# Exercise Generation Prompts
PRACTICE_EXERCISES_PROMPT = """Generate 3 practice exercises for the topic: {topic}
Difficulty level: {difficulty}

Create exercises that:
1. Test understanding of key concepts
2. Build practical skills
3. Progress in complexity

Format each exercise with:
- Clear problem statement
- Any necessary context or constraints
- Expected solution approach

Make exercises engaging and relevant to real-world applications.
"""
