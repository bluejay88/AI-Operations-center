# PET release evidence workflow

PET animation and feature agents submit results to `POST /pet-releases/submissions`. The submission must identify the laptop, agent, PET, feature IDs, implementation summary, artifacts, measured performance, test evidence, audit evidence, and rollback plan.

The API stores every submission as a Brain listener event. An incomplete submission receives targeted speaker feedback and does not create an approval request. A structurally complete submission creates a high-risk `pet_release_candidate` approval for Brain/human review.

Structural completeness is not independent verification. The record therefore remains `submitted_unverified`, and `release_authorized` remains false. Reviewers should inspect artifact contents, reproduce tests and performance measurements, evaluate reduced-motion and accessibility behavior, and verify rollback instructions before choosing `approved`, `needs_changes`, or `rejected` through the existing approval endpoint.

Neither submission nor approval automatically deploys code. A reviewer records `deployed` only after the separately authorized staged/canary/production action succeeds and its deployment evidence is attached to the approval review metadata.

The current rubric is available at `GET /pet-releases/rubric`.
