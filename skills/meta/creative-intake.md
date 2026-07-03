# Creative Intake

Before the research stage, gather user intent through targeted questions.
Do NOT start production on a vague brief.

## Step 0 — Auto-Extraction (always run first)

Call the `prompt_expansion` tool with the user's raw input:

```
prompt_expansion({
  raw_input: "<user message>",
  pipeline_type: "<pipeline if known>",
  target_duration_seconds: <int if stated>
})
```

Read the result:

- **`gaps` is empty** → the user's brief is complete. Skip all questions below.
  Proceed directly to research with the returned `brief_fields` and `scene_plan`.
- **`gaps` is non-empty** → only ask about the listed fields, in the priority order
  returned. Do not ask about fields not in `gaps`.

This means a detailed, professional prompt gets zero follow-up questions.
Multi-turn Q&A only happens when the tool says information is missing.

---

## Asking About Gaps (only when gaps ≠ [])

Don't dump all gaps at once. Ask conversationally — start with the first (highest
priority) gap, then continue based on answers.

**Priority order** (also the order `prompt_expansion` returns gaps):
1. purpose — what the video is FOR (educate, sell, inspire, document, entertain)
2. audience — who watches it (age, expertise, context)
3. platform — where it lives (youtube, instagram, tiktok, linkedin, generic)
4. tone — what it should FEEL like (serious, playful, cinematic, raw, warm, provocative)
5. outcome — what the viewer should DO or FEEL after watching
6. constraints — budget ceiling, timeline, must-include content
7. references — videos or images the user admires (never block on this)

After each user answer, call `prompt_expansion` again with the updated
`conversation_history`. Check the new `gaps` list — stop asking when it is empty
or only contains `references` and `constraints`.

### Stop condition

```
gaps == [] OR (remaining gaps ⊆ {references, constraints})
```

---

## Handling Different Brief Types

### Vague brief ("make me a video about X")

1. Acknowledge the topic — show you understood.
2. Ask only the first gap from `prompt_expansion` output.
3. After each answer, re-call the tool and ask the next gap.
4. Stop when stop condition is met.

### Detailed brief (multi-paragraph or document)

1. Summarize what you understood in 1–2 sentences.
2. Call `prompt_expansion` — if gaps is empty, confirm and move on.
3. If gaps remain, call out only those: "I have a clear picture of audience and tone,
   but I'd love to know — is there a specific outcome you're hoping for?"

### Professional prompt (detailed visual/camera language, 5-aspect style)

`prompt_expansion` will return `gaps: []`. Do not ask any follow-up questions.
Treat `scene_plan` and `video_prompts` from the tool as ready for asset-director.

---

## Final Output

Once `gaps == []`, call `prompt_expansion` one final time with the full
`conversation_history` to get the complete output:

```
prompt_expansion({
  raw_input: "<final user message or summary>",
  conversation_history: [...all prior turns...],
  pipeline_type: "<pipeline>",
  target_duration_seconds: <int>
})
```

Store results in the `brief` artifact:

- `brief_fields` → map directly to brief schema fields (title, hook, tone, etc.)
- `scene_plan` → store in `brief.metadata.scene_plan_draft`
- `video_prompts` → store in `brief.metadata.video_prompts_draft`
- Conversation log → store in `brief.metadata.intake_log` as
  `[{turn: int, role: str, content: str}]`

The intake_brief (informal version) is passed as context to research-director.
Include direct quotes from the user where their language reveals intent.

---

## Handling Reference Video Input

When the user provides a video URL or file as their starting point:

1. **Read the video-reference-analyst skill** (`skills/meta/video-reference-analyst.md`)
   and follow its protocol. Do not run standard creative intake.

2. The VideoAnalysisBrief replaces most intake questions — it provides tone, structure,
   pacing, audience signals, and style information directly from the reference.

3. After video analysis, call `prompt_expansion` with the analysis summary as
   `raw_input` to detect any remaining gaps. The only gaps that typically remain:
   - What topic/subject for YOUR version?
   - Target duration?
   - Narration yes/no?
   - Budget ceiling?

4. Do NOT ask "what should it feel like?" — extract tone from the VideoAnalysisBrief.

---

## What NOT To Do

- Do not present a numbered survey. This is a conversation, not a form.
- Do not ask questions that `prompt_expansion` says are already covered.
- Do not delay production — if `gaps == []`, move on immediately.
- Do not invent answers. Mark inferred fields as such (confidence < 1.0 in tool output).
- Do not assume the user wants an explainer. Listen for signals in tone and vocabulary.
- Do not call `prompt_expansion` more than once per user turn (batch all context).
