# Manual LLM interpretation workflow

This folder contains prompt files for free/manual use with ChatGPT and Claude.

1. Open `chatgpt_5_5_prompt.txt`.
2. Copy all text and paste it into ChatGPT 5.5.
3. Save the answer in `chatgpt_5_5_response.md`.
4. Open `claude_sonnet_4_6_prompt.txt`.
5. Copy all text and paste it into Claude Sonnet 4.6.
6. Save the answer in `claude_sonnet_4_6_response.md`.

Use the response files later for evaluation against your expert/reference
interpretation.

Methodology note for thesis:
The LLMs were accessed through their user-facing web interfaces. The same
structured prompt, generated from the PM4Py output files, was manually provided
to both models. Exact backend model settings such as temperature could not be
controlled, which is treated as a limitation.
