# AI providers in CareerMate

CareerMate supports three provider modes. Select one in **AI provider** in the left navigation; the selected provider is used for CV analysis, job matching, cover letters, and employer-question drafts.

- **Ollama (local):** runs against your local Ollama server. No external AI API billing, but inference speed and CPU/RAM usage depend on your hardware and model.
- **OpenAI API:** uses the OpenAI Responses API for text generation and schema-constrained CV/job-match output.
- **OpenAI-compatible API:** uses a Chat Completions-compatible endpoint for services that document this interface (for example, some third-party routers and hosted model endpoints). Enter that provider's base URL and model ID.

## Configure API credentials

Copy the backend sample file to a local, ignored `.env` file:

```powershell
Copy-Item backend/.env.example backend/.env
```

Edit `backend/.env` and set the credentials for the provider you intend to use:

```dotenv
# OpenAI API
OPENAI_API_KEY=your-api-key-here
CAREERMATE_OPENAI_MODEL=gpt-6-luna

# Optional OpenAI-compatible endpoint
CAREERMATE_OPENAI_COMPATIBLE_API_KEY=your-provider-key-here
CAREERMATE_OPENAI_COMPATIBLE_BASE_URL=https://your-provider.example/v1
CAREERMATE_OPENAI_COMPATIBLE_MODEL=your-model-id
```

Restart FastAPI after changing `.env`. Do not commit `.env` or place a key in a frontend variable, source file, or JSON settings file. `data/settings/ai_settings.json` stores only the provider, model ID, and endpoint URL. The settings endpoint never returns API keys; it exposes only a boolean that indicates whether a key is configured.

For the OpenAI-compatible endpoint, use HTTPS for remote hosts. Plain HTTP is allowed only for loopback URLs such as `http://127.0.0.1:1234/v1`.

## Example: Groq (fast hosted inference)

CareerMate can use providers that are compatible with the OpenAI Chat Completions API without a new integration. For Groq, add your key to `backend/.env`:

```dotenv
CAREERMATE_OPENAI_COMPATIBLE_API_KEY=your-groq-api-key
CAREERMATE_OPENAI_COMPATIBLE_BASE_URL=https://api.groq.com/openai/v1
CAREERMATE_OPENAI_COMPATIBLE_MODEL=openai/gpt-oss-20b
```

Restart FastAPI, open **AI provider**, select **OpenAI-compatible API**, and verify/save the base URL and a model ID currently available to your account. Groq's available models and per-model free-tier limits can change; check its [model list](https://console.groq.com/docs/models) and [rate limits](https://console.groq.com/docs/rate-limits).

## Example: Google Gemini

Google documents OpenAI-compatible access to Gemini. To try it, set the generic provider values in `backend/.env` and then select **OpenAI-compatible API** in CareerMate:

```dotenv
CAREERMATE_OPENAI_COMPATIBLE_API_KEY=your-gemini-api-key
CAREERMATE_OPENAI_COMPATIBLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
CAREERMATE_OPENAI_COMPATIBLE_MODEL=gemini-3.8-flash
```

The example model ID and endpoint follow Google's [OpenAI compatibility documentation](https://ai.google.dev/gemini-api/docs/openai); confirm current model availability and active quota in Google AI Studio. CareerMate's generic adapter sends `response_format: {"type":"json_object"}` for structured tasks, so run **Test connection** and then a CV/job-analysis test to verify the chosen model's compatibility before using it for applications.

**Privacy reminder:** Google currently states that content in the Gemini API free tier may be used to improve Google products. Do not send an unredacted personal CV to a free-tier hosted provider unless you accept its current data policy. With the generic adapter, only one compatible-provider configuration is active at a time; switching between Groq and Gemini currently means changing the configured endpoint/model/key.

## Switch providers

1. Open **AI provider** in the workspace navigation.
2. Select Ollama, OpenAI API, or OpenAI-compatible API.
3. Set the model ID; set a host/base URL when the form asks for one.
4. For an online provider, check the data-sharing acknowledgement. CareerMate sends the prompt content required for the selected operation to that provider. CV analysis sends extracted CV text; job matching sends job details and professional profile facts; application drafting sends professional profile facts and the saved job snapshot.
5. Select **Test connection**. This sends only a short generic ping, not your CV or application data.
6. Select **Save AI settings**. Future AI calls use the selected provider.

The provider test is not a full validation of structured output, matching quality, or application drafts. If the configured model does not support a feature required by the endpoint, use another model supported by your provider.

## Performance

For hosted providers, CareerMate runs up to four selected job-match requests concurrently. Ollama matching remains sequential to avoid overloading the local machine. Successful job matches are cached by job, professional profile, provider, model, and cache version, so a repeated match can be returned without another model call. Changing provider or model uses a different cache key.

Hosted API speed depends on the chosen model, network, service limits, and input size. CareerMate cannot guarantee a specific response time. It also cannot guarantee a specific API bill; review the model and current rates in the provider's dashboard before running large analyses.

## Privacy and billing

Project files remain in local JSON files, but selecting a hosted provider means sending content needed for a task to that provider. Do not enable a cloud provider unless you are comfortable with this data flow. Job matching excludes direct contact details from the candidate prompt, but CV extraction must process the extracted CV text to read the profile fields, and application drafts include the candidate's name when available.

A ChatGPT subscription (Free, Go, Plus, Pro, or other ChatGPT plan) is separate from OpenAI API billing. To use the OpenAI API, create an API key on the API platform and set up API billing separately. Check the current OpenAI API model catalog and billing settings for availability, usage limits, and current prices.

Official references:

- [OpenAI API quickstart](https://developers.openai.com/api/docs/quickstart)
- [OpenAI model catalog](https://developers.openai.com/api/docs/models)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [ChatGPT and API billing are separate](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)
