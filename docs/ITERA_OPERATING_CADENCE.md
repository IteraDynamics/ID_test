# Itera Operating Cadence

## Purpose

The calendar and campaign board should drive the next concrete finish line, not repeat static project summaries.

## Daily mission check

A daily check should answer:

1. Which campaign milestone is active?
2. What single finish line is achievable today?
3. What evidence must exist before stopping?
4. What blocker or decision could prevent completion?

The daily entry should be updated when a milestone changes. It should not carry completed campaign steps forward.

## Weekly campaign review

Review:

- evidence produced;
- knowledge gained or uncertainty reduced;
- open methodological risks;
- research versus engineering time allocation;
- whether infrastructure work remains justified;
- the next milestone and finish line.

## Campaign lifecycle

1. Select and authorize one campaign.
2. Establish the working branch and campaign board state.
3. Complete a specification before implementation.
4. Implement only authorized scope.
5. Run focused tests and real-data verification.
6. Verify replay, artifact integrity, and source integrity where applicable.
7. Run the full regression suite.
8. Update documentation, knowledge registry, and roadmap.
9. Open, review, and merge the PR.
10. Close the campaign and select the next one.

## Work classification

- **Research:** creates or validates market knowledge.
- **Engineering:** builds a capability required by research.
- **Infrastructure:** protects reproducibility, portability, or research velocity.
- **Production:** changes operational behavior.

Research is the default priority. Infrastructure should be scheduled when a concrete reliability or research dependency exists. Production changes require explicit authorization.

## Calendar design rule

Calendar entries should contain the current finish line, acceptance evidence, and at most the next immediate action. Durable context belongs in version-controlled documents.