# Relevance Check Prompt

Use this prompt after reading `manifest.json`, metadata, the first transcript excerpt, and concise context files.

Return only JSON:

```json
{
  "relevance_score": 0,
  "matched_topics": [],
  "summary_mode": "generic",
  "reasoning": ""
}
```

Scoring:
- `7-10`: strongly relevant to Hancom projects, enterprise AI, document AI, RAG, agents, evals, or competitors. Use `contextual`.
- `4-6`: partially relevant or useful by analogy. Use `hybrid`.
- `0-3`: general personal-interest content. Use `generic`.

Rules:
- Base the score on concrete evidence from title, description, transcript excerpt, comments, and context files.
- Keep `reasoning` to one short Korean sentence.
- Do not include unsupported matched topics.
