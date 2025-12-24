
# COGNIX Insights & Evaluation Methodology

## Overview
COGNIX uses advanced argumentation theory and Large Language Models (LLMs) to evaluate the strength and logical validity of user arguments. This document outlines the metrics used, their definitions, and the evaluation methodology.

## Core Metrics

### 1. Toulmin Model Analysis (Radar Chart)
The Toulmin Model breaks an argument down into six functional parts. We score each part on a scale of **0-10** (normalized from 0-5 for visualization).

*   **Claim**: The assertion being made.
    *   *Evaluation*: Is it clear, specific, and debatable?
*   **Data**: The evidence supporting the claim.
    *   *Evaluation*: Is it relevant, accurate, and sufficient?
*   **Warrant**: The logical bridge connecting Data to Claim.
    *   *Evaluation*: Is the reasoning sound? Is it explicit or implicit?
*   **Backing**: Support for the Warrant.
    *   *Evaluation*: Does it provide authority or theoretical support for the reasoning?
*   **Qualifier**: Limits to the Claim (e.g., "usually", "most").
    *   *Evaluation*: Does it accurately reflect the strength of the data?
*   **Rebuttal**: Acknowledgement of counter-arguments.
    *   *Evaluation*: Does it anticipate and address potential objections?

### 2. Advanced Metrics

#### Fallacy Resistance Score (0-100%)
Measures how free the argument is from logical fallacies.
*   **Calculation**: Start at 100%. Deduct points for each fallacy detected based on severity.
    *   *Minor Fallacy (e.g., slight exaggeration)*: -10%
    *   *Major Fallacy (e.g., Ad Hominem, Strawman)*: -25%
    *   *Fatal Fallacy (e.g., Circular Reasoning)*: -50%

#### Logical Consistency Score (0-100%)
Measures the internal coherence of the argument.
*   **Evaluation**: Do the premises contradict each other? Does the conclusion follow logically from the premises?
*   **Scoring**:
    *   100%: Perfectly consistent.
    *   75%: Minor tension between points.
    *   50%: Significant contradiction.
    *   25%: Incoherent.

#### Clarity Score (0-100%)
Measures how easily the argument can be understood.
*   **Evaluation**: Based on sentence structure, vocabulary usage, and organization.
*   **Scoring**:
    *   High (80-100%): Clear, concise, well-structured.
    *   Medium (50-79%): Understandable but wordy or slightly disorganized.
    *   Low (<50%): Confusing, ambiguous, or run-on sentences.

### 3. Common Fallacies Faced
This metric tracks the types of fallacious reasoning the user most frequently encounters or employs.
*   **Method**: Aggregated from historical chat data.
*   **Usage**: Helps tailor the "Defense Mode" training to focus on specific weaknesses (e.g., if a user struggles with *Ad Hominem*, the AI will use it more often in training).

## Implementation Details

### AI Evaluation Prompting
We use a specialized prompt with the `google/gemma-3-27b-it` model to extract these metrics. The prompt enforces a strict JSON schema to ensure consistent parsing.

```json
{
  "elements": { ...Toulmin scores... },
  "fallacy_resistance_score": 85,
  "logical_consistency_score": 90,
  "clarity_score": 95,
  "fallacies_present": ["Hasty Generalization"],
  "improved_statement": "..."
}
```

### Visualization
*   **Radar Chart**: Displays the six Toulmin elements.
*   **Progress Bars/Gauges**: Display the Fallacy Resistance, Consistency, and Clarity scores.
*   **Insights Panel**: Provides a textual summary and improvement tips.
