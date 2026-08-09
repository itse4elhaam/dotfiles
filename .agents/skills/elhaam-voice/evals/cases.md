# Evaluation Cases

Baseline cases for `elhaam-voice`. Each case gives the input text, the expected behavior, and the pass criteria. Run the skill on the input, then check the output against the criteria. The corresponding generic outputs (what a model without the skill produces) and the target outputs are in `baseline.md`.

## Case 1: Tighten a rough client message without removing conviction

**Input**

> hey so i think we should push back on the timeline. the client keeps saying they need everything by friday but honestly their requirements are still changing day to day and i dont think we can promise that and actually deliver something good. we told them two weeks originally and that was a real number. if we say yes to friday we're going to be shipping something we're not proud of and then they'll be unhappy anyway which is worse. i'd rather tell them now its two weeks and explain why than fake it and fail.

**Expected behavior**

Shorten the message, keep every conviction intact: the pushback, the "two weeks was a real number", the refusal to ship something not good, the "worse to fake it and fail" reasoning. No hedging added, no sales softening, no new promises.

**Pass criteria**

- Same position: tell the client now that it's two weeks.
- The strongest original claims survive: "two weeks was a real number", "shipping something we're not proud of", "worse than being honest now".
- No new hedges ("maybe", "perhaps we could consider").
- No em dashes. Rough edges may be cleaned, conviction may not.

## Case 2: Rewrite a reflective paragraph preserving intellectual curiosity

**Input**

> i've been turning over the pricing question for a while now and i still don't have a clean answer. usage based feels right because our cost really does scale with usage, but the moment someone asks "what will this cost me" they want a number, and usage based can't give them one. maybe the answer is a hard cap with a soft warning, or maybe it's just starting flat and learning from real invoices. i don't know yet and that's honestly the interesting part, i get to watch actual customers decide instead of guessing.

**Expected behavior**

Polish the mechanics only: grammar, rhythm, flow. Preserve the open questions, the unresolved state, the curiosity, and the explicit "I don't know yet". Do not resolve the question, do not add certainty.

**Pass criteria**

- "I don't know yet" and both candidate answers survive.
- The closing curiosity (watching real customers decide instead of guessing) survives.
- No fabricated conclusion or confident recommendation added.
- No em dashes.

## Case 3: Refuse to add generic founder-brand language to a natural draft

**Input**

> we fixed the checkout bug. the total now updates when you change the quantity, which it didn't before. if you had two items and changed one, the total stayed wrong until you refreshed. now it's right immediately. that's the whole change.

**Expected behavior**

Return the text essentially unchanged. It already leads with its position and speaks plainly. Do not add brand boilerplate, enthusiasm, or marketing register of any kind.

**Pass criteria**

- No added phrases like "industry-leading", "best-in-class", "we're excited", "seamless", "synergy", "game-changing".
- No added exclamation points or hype.
- The factual, mechanism-level description (updates on quantity change, was wrong until refresh) is preserved or only tightened.
- Any edit is smaller than the original and changes nothing that did not need changing.

## Case 4: Distinguish a real factual risk from harmless strong wording

**Input** (two sentences in one message)

> this is the best option we have right now, no question. and it's guaranteed to never go down because we built it ourselves.

**Expected behavior**

Keep the first sentence, a bounded, defensible strong opinion. Fix only the second, an unsupported guarantee that creates factual and reputational risk. Correct the minimum span.

**Pass criteria**

- "best option we have right now, no question" survives, possibly lightly tightened, with conviction intact.
- The "guaranteed to never go down" claim is changed to a true, limited claim (for example, "it's been up for a year straight" or "we run it ourselves so we can fix it fast").
- Only the risky claim is edited; the safe strong wording is untouched.
- No em dashes.

## Case 5: Final pass returning "send it" when no material edit is needed

**Input**

> Shipping tomorrow. It's the smallest version that answers the question we actually need answered, and I'd rather see real usage than guess. If it breaks, we'll know within a day.

**Expected behavior**

This is already in his voice. The final check returns "send it" with no edits, or at most a note of a trivial, optional tweak. No gratuitous rewrites.

**Pass criteria**

- Verdict is "send it".
- Zero substantive edits made; any note is flagged as optional.
- No em dashes.
- No restated version of the text returned as an improvement.

## Case 6: Preserve an unusual but effective original phrase rather than normalizing it

**Input**

> the settings page is fine except for the part where the dropdown forgets where you were. you open it, scroll, close it, and when you come back it's back at the top. it's the kind of bug that makes you think the whole app is broken even though it's one component.

**Expected behavior**

Keep "the dropdown forgets where you were". It is distinctive, concrete, and exactly right. Do not normalize it into technical or corporate language. Fix only real issues (none here beyond light tidying).

**Pass criteria**

- "forgets where you were" appears verbatim in the output.
- No replacement with "fails to maintain scroll position" or similar normalized phrasing.
- The second sentence's point (one small bug reads as a broken app) survives.
- No em dashes.
