---
name: upwork-proposal
description: Write short, proof-led Upwork proposals using a locked four-beat structure: hook, exactly three build bullets, client proof, then a one-question CTA. Use when drafting or rewriting a complete Upwork proposal, cover letter, bid, or job application for Elhaam.
---

# Upwork Proposal

Use this skill as the primary instruction set for Upwork proposal work.

## Instruction precedence and execution flow

Apply instructions in this order:

1. The user's instructions for the current request.
2. Any proposal wording, sentence, hook, proof, bullet, CTA, or partial draft supplied by the user.
3. This skill.
4. General writing defaults.

A user's current instruction supersedes this skill, even when it changes the format, length, tone, number of bullets, CTA, or whether to include an explanation.

If the user supplies any part of the proposal, use it as the starting point and preserve it unless the user asks for rewriting, correction, expansion, or replacement. Fill only the missing parts that are necessary. Do not silently replace user-provided wording with a new version.

When a job is provided:

1. Qualify it using the deterministic job-fit or proposal-qualification rules available in the active system.
2. If it does not qualify, say so briefly and do not write a proposal unless the user explicitly asks for one anyway.
3. If it qualifies, produce the first proposal draft immediately in the same response. Do not stop after qualification, ask for permission to draft, or provide only an analysis.
4. Keep qualification reasoning separate from the proposal only when the user asks for it or when the job does not qualify. When returning a qualifying job's draft by default, prioritize the proposal.

The structure below is the default for a qualifying job. It is subordinate to the user's current instructions and any wording they supplied.

## 1. Hook

Open with 1-2 short sentences that connect the strongest relevant proof to the client's exact problem.

- Lead with evidence, not enthusiasm.
- Prefer a named comparable project, quantified outcome, scale, or directly relevant domain.
- Mirror the client's nouns where natural: ecommerce, inventory, booking, marketplace, POS, Next.js, SEO, etc.
- Do not say "I am excited", "I would love", "I am a perfect fit", or introduce Elhaam by title.
- Keep the hook under 45 words.

Then write exactly:

`Here's how I will build <project/product/outcome> for you:`

Completion: the first two lines make the client understand why Elhaam is unusually relevant before they reach the bullets.

## 2. Three build bullets

Write exactly **3 bullets**. No more, no fewer.

Each bullet must:

- start with a bold 1-3 word label
- contain one compact sentence after the label
- describe what will be built, how the risky/core behavior will work, or how it will ship
- be specific to the posted job
- fit comfortably on a phone screen

Prefer this order when it fits:

1. core user/product experience
2. backend, data, integrations, or business rules
3. admin, delivery, reliability, performance, or launch

Do not restate the full job description. Collapse adjacent requirements into one coherent system.

Completion: the three bullets cover the core product without becoming a feature inventory.

## 3. Client proof

Add one short proof paragraph after the bullets.

Choose the closest **different** proof from the hook when possible.

Evidence may come only from facts already available to the agent through the user's supplied context, profile, attached material, or verified project data.

- Prefer a client quote when one is relevant.
- Otherwise use one quantified result or comparable shipped product.
- Never invent a metric, testimonial, client, responsibility, technology, or project outcome.
- Do not stack multiple testimonials or turn this into a case-study paragraph.
- Keep it to 1-2 sentences.
- If no verified proof exists anywhere in context, ask for one instead of fabricating it.

Completion: the proof answers "can this person actually deliver?" without repeating the hook.

## 4. CTA

End with exactly **one short question** that advances the project.

Good CTA targets:

- ideal launch date
- first integration or platform
- MVP boundary
- which workflow should ship first
- a concrete unresolved product decision from the post

Do not ask for a call. Do not write multiple questions. Do not append a sign-off after the question.

Completion: the final line is easy for the client to answer in one sentence.

## Output contract

Return only the proposal in this shape:

```text
<hook>

Here's how I will build <project/product/outcome> for you:

• **<label>:** <one compact sentence>
• **<label>:** <one compact sentence>
• **<label>:** <one compact sentence>

<client proof>

<one-question CTA>
```

Hard constraints:

- 90-160 words by default
- exactly 3 bullets
- exactly 1 question mark, in the CTA
- no headings such as "Hook", "Proof", or "CTA" in the proposal
- no greeting or sign-off
- no generic claims that are not backed by evidence
- no more than one parenthetical aside
- use the client's terminology over agency jargon
- if the user supplies wording, preserve its factual claims unless asked to change them

Before replying, silently check the output against every hard constraint. If one fails, rewrite before returning it.
