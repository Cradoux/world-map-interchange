# Governance (draft)

This is a proposal for how decisions could be made. It is itself open for discussion and is expected to change once
participating developers have had their say.

## Principles

1. **Equal technical input.** Each participating tool (for example Dayside, Rock3, Gleba and World Climate Lab, if their
   developers choose to take part) has an equal voice on technical questions. No tool's internal format is the default
   answer, including the tool whose developer started this repository.
2. **Evidence over preference.** Decisions should rest on concrete use cases, example packages and implementation
   experience.
3. **Small and implementable.** Prefer features that two independent implementations can get right from the text alone.
4. **Transparency.** Decisions and open questions are recorded in public issues, in [docs/open-decisions.md](docs/open-decisions.md)
   and in the [changelog](CHANGELOG.md).
5. **No implied endorsement.** Participating in discussion does not mean endorsing the draft or committing to implement it.
   Tools are listed as participants only with their developer's agreement.

## Current state

- The repository was created by the Dayside developer as a starting point. No maintainers have been appointed beyond the
  repository owner, and nobody has been granted access or sent invitations through this repository.
- Until participants agree on a process, the repository owner merges changes after giving reasonable time for comment.
  Normative changes should get at least 14 days of public discussion during 0.x.

## Proposed process (to be agreed)

- **Participants.** A developer of any tool that produces or consumes WMI packages may ask to be listed as a participant,
  with one technical representative per tool.
- **Decisions.** Lazy consensus: a proposal that has been open for discussion for 14 days with no sustained objection from a
  participant is accepted. Sustained objections are resolved by discussion. If that fails, they are resolved by a simple
  majority of participating tools, one vote per tool, with the reasons recorded.
- **Maintainers.** Participants may agree to appoint maintainers with merge rights. Maintainers carry out decisions; they
  do not get extra votes.
- **Releases.** A draft version is tagged once its spec, schemas, registry, validator and examples agree and CI passes.
  Leaving "experimental" status should require at least two independent implementations that interoperate on the examples.
- **Neutral home.** If several tools participate, the repository may move to a neutral GitHub organisation.

## Scope boundaries

Application-specific import/export adapters live in each application's own codebase or separate repositories. This
repository holds the shared specification, schemas, registry, reference tools and synthetic examples.
