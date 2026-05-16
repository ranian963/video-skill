# Tech Stack Context

## AI Platform
- LiteLLM for model routing and provider abstraction.
- Langfuse for tracing, prompt/version observability, and evaluation workflows.
- LangFlow and RAGFlow as reference points for builder-style agent/RAG UX.

## Infrastructure
- Kubernetes and containerized services for enterprise deployment.
- GPU servers, including H100-class environments, may be available for local or sensitive inference paths.

## Data And Evaluation
- Prefer structured traces, reproducible benchmarks, and regression-oriented eval sets.
- For document work, visual/rendered output checks are as important as text-level metrics.
