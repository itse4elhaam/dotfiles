---
name: requirements-edge-cases
description: Use this skill when the user gives you initial requirements, asks you to build something e2e or ship a fix.
---

# Requirements edge cases

Your purpose is to dissect the issue more than just the surface that's visibile.

You do this by walking down the decision trees and logical pathways of the solution to the given requirements.

For all of the pathways, figure out which assumptions are holding it up and what if they are not present?

Then, before implementing anything **dry run** all of the seams of this implementation (spend time on this)

As the result of the dry run, figure out the loopholes in your implementation, positive cases failure, negative cases failure and edge cases.

Inform the user about the cases that you have figured and align with them on this: Are they within the scope of this implementation or going outside of it?

If they are within the implementation scope, fix them within the part of the first ongoing implementation and include them in the todo lists/chunking you do.

The ultimate goal is reduce the rework required from requirements to shipping.
