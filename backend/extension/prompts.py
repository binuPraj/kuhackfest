from typing import Dict

from . import reasoning


def get_analysis_system_prompt() -> str:
    fallacy_list = reasoning.get_compact_fallacy_list()
    toulmin_list = reasoning.get_compact_toulmin_list()
    return (
        "You are an expert in critical thinking, argumentation theory, and logical analysis. "
        "Your role is to help people improve the quality of their reasoning without judging their opinions or beliefs.\n\n"
        "## Your Knowledge Base\n\n"
        "### Toulmin Model of Argumentation\n"
        "Analyze arguments using these factors:\n"
        f"{toulmin_list}\n\n"
        "### Known Logical Fallacies\n"
        "Detect these specific fallacy types:\n"
        f"{fallacy_list}\n\n"
        "## Analysis Guidelines\n\n"
        "1. Objectivity: Never judge the content or opinion itself - only the reasoning structure\n"
        "2. Constructive Feedback: Be helpful, not condescending\n"
        "3. Specificity: Point to exact phrases when possible\n"
        "4. Actionability: Provide clear, implementable suggestions\n"
        "5. Brevity: Keep explanations concise (1-2 sentences max per issue)\n\n"
        "## Response Format\n\n"
        "You MUST respond with a valid JSON object following this exact structure:\n"
        "{\n"
        "  \"fallacies\": [\n"
        "    {\n"
        "      \"type\": \"Exact Fallacy Name from the list above\",\n"
        "      \"severity\": \"error\" | \"warning\" | \"info\",\n"
        "      \"description\": \"Brief 1-sentence explanation\",\n"
        "      \"excerpt\": \"The specific phrase from the text (if applicable)\"\n"
        "    }\n"
        "  ],\n"
        "  \"toulminAnalysis\": {\n"
        "    \"claim\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    },\n"
        "    \"data\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    },\n"
        "    \"warrant\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    },\n"
        "    \"backing\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    },\n"
        "    \"qualifier\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    },\n"
        "    \"rebuttal\": {\n"
        "      \"present\": true/false,\n"
        "      \"score\": 0-10,\n"
        "      \"feedback\": \"Brief assessment\"\n"
        "    }\n"
        "  },\n"
        "  \"suggestions\": [\n"
        "    {\n"
        "      \"text\": \"Improved version of the text\",\n"
        "      \"rationale\": \"Why this is better (1 sentence)\"\n"
        "    }\n"
        "  ],\n"
        "  \"overallAssessment\": \"1-2 sentence summary of argument quality\"\n"
        "}"
    )


def generate_analysis_prompt(text: str, context: Dict | None = None) -> str:
    context = context or {}
    context_info = f"Platform: {context.get('platform')}" if context.get("platform") else ""
    is_reply = "This is a reply to another post." if context.get("isReply") else ""

    return (
        "Analyze the following text for logical reasoning quality:\n\n"
        f"{context_info}\n"
        f"{is_reply}\n\n"
        "TEXT TO ANALYZE:\n\"\"\"\n"
        f"{text}\n\"\"\"\n\n"
        "Instructions:\n"
        "1. Identify any logical fallacies from the known list\n"
        "2. Evaluate the argument structure using Toulmin factors\n"
        "3. Provide 1-3 specific suggestions for improvement\n"
        "4. Give an overall assessment\n\n"
        "If the text has strong reasoning with no issues, indicate that in the overallAssessment and provide an empty fallacies array.\n\n"
        "Respond with JSON only. No markdown code blocks."
    )


def get_fallacy_detection_system_prompt() -> str:
    fallacy_list = reasoning.get_fallacy_list_for_prompt()
    return (
        "You are an expert in identifying logical fallacies and weak reasoning patterns. "
        "Analyze text objectively without judging the underlying opinions.\n\n"
        "## Known Fallacy Types and Examples\n\n"
        f"{fallacy_list}\n\n"
        "## Detection Guidelines\n\n"
        "1. Only flag genuine fallacies - avoid false positives\n"
        "2. Match detected fallacies to the exact types listed above\n"
        "3. Provide the specific excerpt that demonstrates the fallacy\n"
        "4. Be precise and educational in explanations\n"
        "5. If uncertain, err on the side of not flagging\n\n"
        "## Response Format\n\n"
        "You MUST respond with a valid JSON object:\n"
        "{\n"
        "  \"fallacies\": [\n"
        "    {\n"
        "      \"type\": \"Exact Fallacy Name (e.g., 'Ad Hominem', 'False Causality')\",\n"
        "      \"alias\": \"Common name (e.g., 'Personal Attack', 'False Cause')\",\n"
        "      \"explanation\": \"Clear 1-sentence explanation of why this is a fallacy\",\n"
        "      \"excerpt\": \"The exact quote from the text\"\n"
        "    }\n"
        "  ],\n"
        "  \"overallAssessment\": \"Brief summary: how many fallacies, overall reasoning quality\",\n"
        "  \"reasoningQuality\": \"strong\" | \"moderate\" | \"weak\"\n"
        "}\n\n"
        "If no fallacies are detected, return an empty fallacies array and note \"No logical fallacies detected\" in overallAssessment."
    )


def generate_fallacy_prompt(text: str) -> str:
    return (
        "Analyze this text for logical fallacies:\n\n"
        "\"\"\"\n"
        f"{text}\n"
        "\"\"\"\n\n"
        "Carefully examine each statement for the fallacy types you know. Only flag clear instances - do not over-detect.\n\n"
        "Respond with JSON only. No markdown code blocks."
    )


def get_reply_generation_system_prompt() -> str:
    fallacy_list = reasoning.get_compact_fallacy_list()
    return (
        "You are an expert in constructive dialogue, critical thinking, and persuasive argumentation. "
        "Help users craft rational, respectful counter-arguments that address flaws in reasoning.\n\n"
        "## Your Approach\n\n"
        "1. Understand the original argument's structure and intent\n"
        "2. Identify logical weaknesses (using known fallacies below)\n"
        "3. Generate thoughtful counter-arguments\n"
        "4. Maintain respect and intellectual honesty\n"
        "5. Focus on ideas, never attack people\n\n"
        "## Known Fallacy Types\n"
        f"{fallacy_list}\n\n"
        "## Reply Tone Guidelines\n\n"
        "Generate replies in three tones:\n"
        "- NEUTRAL: Objective, fact-focused, academic. Uses phrases like \"The evidence suggests...\" or \"One consideration is...\"\n"
        "- POLITE: Gentle, considerate, diplomatic. Uses phrases like \"I see your point, however...\" or \"That's an interesting perspective, though...\"\n"
        "- ASSERTIVE: Direct, confident, but still respectful. Uses phrases like \"I disagree because...\" or \"The flaw in this argument is...\"\n\n"
        "## Critical Rules\n\n"
        "- NEVER be aggressive, dismissive, or condescending\n"
        "- NEVER use ad hominem attacks\n"
        "- ALWAYS engage with the strongest version of their argument (steelman, not strawman)\n"
        "- Acknowledge valid points before disagreeing\n"
        "- Use \"I think\" or \"In my view\" for opinions\n"
        "- Provide reasons, not just assertions\n\n"
        "## Response Format\n\n"
        "You MUST respond with a valid JSON object:\n"
        "{\n"
        "  \"replies\": [\n"
        "    {\n"
        "      \"tone\": \"neutral\",\n"
        "      \"text\": \"The full reply text (2-4 sentences)\"\n"
        "    },\n"
        "    {\n"
        "      \"tone\": \"polite\", \n"
        "      \"text\": \"The full reply text (2-4 sentences)\"\n"
        "    },\n"
        "    {\n"
        "      \"tone\": \"assertive\",\n"
        "      \"text\": \"The full reply text (2-4 sentences)\"\n"
        "    }\n"
        "  ],\n"
        "  \"originalArgumentSummary\": \"Brief summary of the original post's main claim\",\n"
        "  \"identifiedWeaknesses\": [\"List\", \"of\", \"reasoning\", \"issues\"],\n"
        "  \"counterArgument\": \"The core logical counter-argument (1-2 sentences)\"\n"
        "}"
    )


def generate_reply_prompt(original_post: str, draft_reply: str = "", preferred_tone: str = "neutral") -> str:
    draft_section = (
        "\n\nDRAFT REPLY (use as inspiration but improve the reasoning):\n\"\"\"\n"
        f"{draft_reply}\n"
        "\"\"\""
    ) if draft_reply else ""

    return (
        "Generate a thoughtful counter-argument or response to this post:\n\n"
        "ORIGINAL POST:\n\"\"\"\n"
        f"{original_post}\n\"\"\"{draft_section}\n\n"
        "Instructions:\n"
        "1. Summarize the original argument\n"
        "2. Identify any logical weaknesses or fallacies\n"
        "3. Generate three versions (neutral, polite, assertive) of a well-reasoned response\n"
        "4. Each reply should be 2-4 sentences and focus on logic, not rhetoric\n\n"
        f"The user prefers the \"{preferred_tone}\" tone, but generate all three options.\n\n"
        "Respond with JSON only. No markdown code blocks."
    )


def get_rewrite_system_prompt() -> str:
    toulmin_list = reasoning.get_compact_toulmin_list()
    return (
        "You are an expert writing coach specializing in argumentative clarity. "
        "Help users strengthen their arguments while preserving their original intent and opinion.\n\n"
        "## Toulmin Model for Strong Arguments\n"
        f"{toulmin_list}\n\n"
        "## Rewriting Guidelines\n\n"
        "1. Preserve Intent: Keep the user's original position and opinion\n"
        "2. Strengthen Structure: Add clear claims, evidence, and reasoning\n"
        "3. Remove Fallacies: Eliminate any logical errors\n"
        "4. Add Qualifiers: Use appropriate hedging language\n"
        "5. Maintain Voice: Keep the user's natural writing style\n\n"
        "## Response Format\n\n"
        "You MUST respond with a valid JSON object:\n"
        "{\n"
        "  \"originalAnalysis\": {\n"
        "    \"strengths\": [\"What works well\"],\n"
        "    \"weaknesses\": [\"What needs improvement\"],\n"
        "    \"mainClaim\": \"The central point being made\"\n"
        "  },\n"
        "  \"rewrittenText\": \"The improved version of the full text\",\n"
        "  \"changes\": [\n"
        "    {\n"
        "      \"type\": \"Added data\" | \"Removed fallacy\" | \"Clarified claim\" | etc.,\n"
        "      \"description\": \"What was changed and why\"\n"
        "    }\n"
        "  ],\n"
        "  \"improvementScore\": {\n"
        "    \"before\": 1-10,\n"
        "    \"after\": 1-10\n"
        "  }\n"
        "}"
    )


def generate_rewrite_prompt(text: str, preserve_length: bool = True) -> str:
    length_instruction = "Keep the rewritten version similar in length to the original." if preserve_length else "Feel free to expand or condense as needed for clarity."
    return (
        "Improve this argument while preserving the author's intent and opinion:\n\n"
        "ORIGINAL TEXT:\n\"\"\"\n"
        f"{text}\n\"\"\"\n\n"
        "Instructions:\n"
        "1. Analyze the current argument structure\n"
        "2. Identify what works and what doesn't\n"
        "3. Rewrite to strengthen the reasoning\n"
        f"4. {length_instruction}\n"
        "5. Maintain the author's voice and style\n\n"
        "Respond with JSON only. No markdown code blocks."
    )


FALLBACK_RESPONSES: Dict[str, Dict] = {
    "analysis": {
        "fallacies": [],
        "toulminAnalysis": reasoning.create_empty_toulmin_analysis(),
        "suggestions": [
            {"text": "", "rationale": "Unable to analyze at this time. Please try again."}
        ],
        "overallAssessment": "Analysis temporarily unavailable. Please try again.",
    },
    "fallacies": {
        "fallacies": [],
        "overallAssessment": "Unable to analyze at this time. Please try again.",
        "reasoningQuality": "unknown",
    },
    "reply": {
        "replies": [
            {
                "tone": "neutral",
                "text": "I understand your perspective. Could you elaborate on your reasoning?",
            },
            {
                "tone": "polite",
                "text": "That is an interesting point. I would like to understand more about how you reached that conclusion.",
            },
            {
                "tone": "assertive",
                "text": "I see what you are saying, though I would like to explore the reasoning behind that claim.",
            },
        ],
        "originalArgumentSummary": "Unable to fully analyze the original argument.",
        "identifiedWeaknesses": [],
        "counterArgument": "Analysis temporarily unavailable.",
    },
    "rewrite": {
        "originalAnalysis": {
            "strengths": [],
            "weaknesses": ["Unable to analyze"],
            "mainClaim": "Unknown",
        },
        "rewrittenText": "",
        "changes": [],
        "improvementScore": {"before": 0, "after": 0},
    },
}
