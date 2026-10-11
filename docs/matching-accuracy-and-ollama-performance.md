# Matching accuracy and Ollama performance

## Why a profile fact could be reported as missing

The previous matcher omitted `personal.location` from the candidate facts sent to the model. It also trusted the model's classification for named languages, and accepted an LLM-supplied `critical` label even when the advert only said a criterion was required rather than a true eligibility gate. Old results could remain visible through the match cache.

The updated matcher: 

- Includes the saved city/country and language list in the candidate evidence, while still excluding name, email, phone number and profile URLs.
- Deterministically checks explicit saved locations and named languages when the advertisement contains a matching criterion. For a language level such as fluent/C1 or strong communication, a profile that only lists `English` becomes **partially supported**, not absent; it does not invent a proficiency level.
- Treats C#/.NET and web-application experience as partial related evidence for an MVC/Razor requirement only when that related evidence exists. It does not claim hands-on MVC/Razor experience unless it is specifically stated.
- Derives criticality from explicit hard gates (for example numeric minimum-years requirements, explicit mandatory language proficiency, work authorization, or explicit location/onsite constraints). The model's `critical` label alone is not trusted.
- Increments the match-cache version, forcing old reports to be regenerated.

Always save the reviewed profile before matching. The frontend does this when Analyze matches is clicked, but if the profile has been edited in another browser/tab, reload and save it before relying on results.

## Why local matching was slow

The previous matching call allowed up to 4,600 generated tokens and requested a 16,384-token context. On a CPU-only machine, producing a long structured JSON response can take several minutes; the model also competes for system RAM/CPU. Ollama's model and runtime options affect memory and speed. See the [Ollama API options](https://github.com/ollama/ollama/blob/main/docs/api.md) and [official model library](https://ollama.com/library/qwen3).

The updated matcher caps output at 2,400 tokens and context at 8,192, and asks for 10–18 material criteria, expanding for longer adverts. It still includes up to 25 criteria for detailed listings. This is a trade-off: lower latency, but avoid excessively long evidence blurbs.

### Recommended lower-resource local model

The default for new installations is `qwen3:4b`. Ollama lists its Q4_K_M model at roughly 2.5 GB, compared with the Gemma 4 E4B model family at roughly 6.6–9.5 GB. Download size is not the same as total runtime RAM, but the smaller model is a reasonable first choice on a computer that reaches high memory usage. Sources: [Qwen3 model library](https://ollama.com/library/qwen3/tags), [Gemma 4 model library](https://ollama.com/library/gemma4/tags).

In PowerShell:

```powershell
ollama pull qwen3:4b
ollama list
ollama ps
```

Then open CareerMate → AI provider, set the Ollama model ID to `qwen3:4b`, and save. This is necessary even if `backend/.env.example` contains the new default: an existing `data/settings/ai_settings.json` preserves the model already selected in your app.

If the machine is still struggling, try `qwen3:1.7b` (lower resource use, but generally weaker output) and compare its assessments against a few known requirements. Do not treat either model's score as an employment probability.

### What to measure

1. Test a single long advert with the current model and note the time.
2. Switch to `qwen3:4b` and repeat the same advert.
3. Check `ollama ps` to see which model is loaded and whether it is using the expected backend.
4. Compare the generated requirement list against the original advert, especially numeric experience thresholds, language level, work authorization, and named frameworks.
5. Use a hosted model only if the provider's data policy is appropriate for the CV content and you understand any free-tier quota/terms.
