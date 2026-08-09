# Baseline Eval Record

For each case in `cases.md`: the draft output a model produces WITHOUT the skill (generic), the target output WITH the skill, and what changed. This is the fidelity check: it documents the specific improvement `elhaam-voice` is expected to produce. Generic outputs show the failure modes the skill exists to kill: corporate fog, throat-clearing, hedged conviction, normalized phrasing, em dashes, and added hype.

## Case 1: Tighten a rough client message without removing conviction

**Generic (before the skill)**

> I think we should reconsider the timeline and perhaps push back on the client's request. While I understand their desire to deliver by Friday, their requirements are still evolving, and it may not be realistic to promise a delivery we can fully stand behind. We originally estimated two weeks, which was a well-considered figure. Delivering a suboptimal product by Friday would likely leave the client dissatisfied in the long run, which would be counterproductive. I would recommend communicating our two-week timeline now, with a clear explanation, rather than committing to an unrealistic deadline.

**Target (after the skill)**

> I want to push back on the timeline. The client's requirements are still changing day to day, so promising Friday means shipping something we're not proud of. Two weeks was a real number. Better to tell them now, with the reason, than fake it and fail.

**What improved**

- Conviction restored: "push back", "was a real number", "fake it and fail" carry his voice.
- Filler reasoning and throat-clearing removed ("While I understand", "well-considered figure", "counterproductive").
- No "may be", "perhaps", "I would recommend" hedging. Shorter by more than half.

## Case 2: Rewrite a reflective paragraph preserving intellectual curiosity

**Generic (before the skill)**

> I have been contemplating the pricing strategy for some time, and it remains an open question. Usage-based pricing aligns well with our cost structure, yet customers invariably desire a fixed number when asked about cost, which usage-based pricing cannot readily provide. One potential solution might be a hard cap with a warning threshold, or alternatively, a flat starting price informed by actual invoice data. Ultimately, this requires further analysis and customer feedback before a definitive decision can be made.

**Target (after the skill)**

> I keep turning over the pricing question and I still don't have a clean answer. Usage-based feels right because our cost really does scale with usage, but the moment someone asks "what will this cost me" they want a number, and usage-based can't give them one. Maybe the answer is a hard cap with a soft warning, or maybe it's starting flat and learning from real invoices. I don't know yet, and that's the interesting part: I get to watch actual customers decide instead of guessing.

**What improved**

- Curiosity preserved: "I don't know yet, and that's the interesting part" survives, where the generic version quietly resolved the tension into "requires further analysis".
- The concrete dilemma (cost scales with usage vs customers want a number) stays vivid.
- No false certainty, no committee phrasing ("it remains an open question" vs "I still don't have a clean answer").

## Case 3: Refuse to add generic founder-brand language to a natural draft

**Generic (before the skill)**

> We're thrilled to announce a significant improvement to our checkout experience! Our team has worked diligently to resolve a persistent issue, delivering a seamless and reliable payment flow. Now, when you update your quantity, the total updates instantly, ensuring a frictionless, best-in-class user journey. We remain committed to excellence and look forward to continuing to enhance your experience!

**Target (after the skill)**

> We fixed the checkout bug. The total now updates when you change the quantity, which it didn't before. If you had two items and changed one, the total stayed wrong until you refreshed. Now it's right immediately. That's the whole change.

**What improved**

- The natural draft is returned essentially unchanged instead of being rewritten into a press release.
- "Seamless", "best-in-class", "frictionless", "thrilled", "committed to excellence" are absent because no hype was added in the first place.
- The mechanism-level description ("stayed wrong until you refreshed") survives, which the generic version erased.

## Case 4: Distinguish a real factual risk from harmless strong wording

**Generic (before the skill)**

> This is arguably one of the best options we have at this time, and it's engineered for maximum reliability with our proprietary infrastructure ensuring continuous uptime.

**Target (after the skill)**

> This is the best option we have right now, no question. And it's been up for a year straight, so the track record is there.

**What improved**

- The bounded conviction is kept and sharpened: "no question" survives, where the generic version weakened it to "arguably one of the best".
- Only the unsupportable guarantee ("guaranteed to never go down", softened to "ensuring continuous uptime") was corrected to a true, checkable claim.
- The smallest span was edited: the safe sentence and the risky claim were handled differently, exactly as required.

## Case 5: Final pass returning "send it" when no material edit is needed

**Generic (before the skill)**

> I wanted to take a moment to confirm that we are proceeding with the launch as scheduled for tomorrow. This release represents the minimal viable iteration that addresses the core question we need to answer, and I believe it is preferable to validate against real-world usage rather than relying on assumptions. Should any issues arise, we will be well-positioned to identify and address them promptly.

**Target (after the skill)**

> Shipping tomorrow. It's the smallest version that answers the question we actually need answered, and I'd rather see real usage than guess. If it breaks, we'll know within a day.
>
> Verdict: send it. No material edits needed.

**What improved**

- The finished input is recognized as already in his voice, and the output is the verdict "send it" instead of a gratuitous rewrite.
- The generic version proves the failure mode: it "improved" the text by padding it with "I wanted to take a moment", "well-positioned", and "minimal viable iteration", losing the rhythm entirely.
- The skill's branch 3 returns a verdict, not a rewrite, when the draft already passes.

## Case 6: Preserve an unusual but effective original phrase rather than normalizing it

**Generic (before the skill)**

> The settings page is generally functional, with the exception of a known issue in the dropdown component: the scroll position is not persisted when the menu is closed and reopened. This appears to reset the view to the top. While this is a minor component-level defect, its impact on perceived product quality is disproportionately negative.

**Target (after the skill)**

> The settings page is fine except for the part where the dropdown forgets where you were. You open it, scroll, close it, and when you come back it's back at the top. It's the kind of bug that makes you think the whole app is broken even though it's one component.

**What improved**

- "the dropdown forgets where you were" survives verbatim; the generic version normalized it into "the scroll position is not persisted", which is the exact failure the skill forbids.
- The human consequence (one small bug reads as a broken app) survives instead of the abstract "disproportionately negative impact on perceived product quality".
- Nothing else needed changing, so nothing else changed.
