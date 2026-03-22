You are reviewing whether the recent implementation for Task {task_index} ("{title}") matches its specification.

## What Was Requested

Goal: {goal}
Files to touch: Create {files_to_create}, Modify {files_to_modify}, Remove {files_to_remove}
Success Criteria: {success_criteria}

## Reference Documentation

Read these doc sections for the authoritative specification: {doc_sections}

## CRITICAL: Do Not Trust the Report

You MUST verify everything independently. Read the actual code they wrote in the files listed above. Compare actual implementation to requirements line by line.

## Your Job

Verify:
1. **Missing requirements:** Did they implement everything requested?
2. **Extra/unneeded work:** Did they over-engineer or add "nice to haves" that weren't requested?
3. **Misunderstandings:** Did they solve the wrong problem?

Report back to the main agent:
- ✅ Spec compliant (if everything matches)
- ❌ Issues found: [list specifically what's missing or extra]
