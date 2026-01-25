# Model Setup Guide

Smart Second Brain uses specialized models for different tasks to maximize accuracy.

## Required Models

Pull these models before starting:

```bash
# Task extraction (best at parsing intent from messy notes)
ollama pull deepseek-r1:14b

# Entity recognition & routing (handles context well)
ollama pull qwen2.5:32b

# General purpose & clustering
ollama pull qwen2.5:14b

# Fallback (lightweight)
ollama pull llama3.1:8b
```

## Model Assignments

| Task | Model | Why |
|------|-------|-----|
| Task Extraction | deepseek-r1:14b | Reasoning model - better at understanding implicit tasks |
| Entity Recognition | qwen2.5:32b | Larger context - catches people/projects in complex text |
| Domain Routing | qwen2.5:14b | Fast, accurate for classification |
| Clustering | qwen2.5:14b | Good at topic segmentation |
| Fallback | llama3.1:8b | Lightweight backup |

## VRAM Requirements

- deepseek-r1:14b: ~12GB
- qwen2.5:32b: ~20GB  
- qwen2.5:14b: ~10GB
- llama3.1:8b: ~6GB

**Total peak usage:** ~24GB (when running 32b model)

Your RTX 3090 (24GB) handles this perfectly.

## Configuration

Edit `.env`:

```bash
OLLAMA_TASK_EXTRACTION_MODEL=deepseek-r1:14b
OLLAMA_ENTITY_RECOGNITION_MODEL=qwen2.5:32b
OLLAMA_ROUTING_MODEL=qwen2.5:14b
OLLAMA_CLUSTERING_MODEL=qwen2.5:14b
```

## Testing

```bash
python src/main.py test
```

Checks all models are available.

## Fallback Behavior

If a model fails:
1. Retries 3 times
2. Falls back to llama3.1:8b
3. Logs warning

## Performance

- Task extraction: ~5-10s (deepseek-r1 is slower but more accurate)
- Routing: ~2-3s
- Clustering: ~3-5s

Slower than single model but significantly better quality.
