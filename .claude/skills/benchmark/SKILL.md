---
name: benchmark
description: >
  Generate LaTeX benchmark evaluation documents for mathematical research
  problems. Triggers when the user provides problem statements, reference
  solutions, rubrics, and model answers for scoring comparison. Produces a
  single compilable .tex file with problem, rubric, comparison, review,
  and appendix sections.
---
# Mathematical Benchmark Evaluation Document — LaTeX Generation

This skill produces a complete, compilable English `.tex` file following a fixed academic evaluation template for mathematical research problems.

The document covers: problem statement, origin and difficulty, reference solution, rubric, model comparison with scoring, failure diagnosis.

## Inputs

The 6 input items are provided in a structured Markdown file (typically `input.md`
in the session workspace). The system prompt tells you the exact file path.
**Read the file first**, then process its sections:

1. **Problem**: A research-level mathematical problem (may be in Chinese — translate to English)
2. **Origin of the Problem**: Source, domain, background information
3. **Solution to Problem**: GPT's correct answer, serving as the reference solution (VERBATIM TRANSLATE — do NOT alter, compress, or reorganize)
4. **Rubric**: Scoring criteria, key concepts/techniques, point allocations
5. **Doubao Model's Answer**: Doubao's response (VERBATIM TRANSLATE for the appendix — do NOT correct errors)
6. **Doubao Model's Answer Analysis**: Analysis of Doubao's failures

## Output

Write a single, complete, compilable English `.tex` file to the output path
specified by the system prompt. Do NOT output the tex content as chat text;
use the Write tool to create the file.

**Before writing, read `references/template-structure.md` for the full structural specification and examples.**

## Document Skeleton

The output `.tex` must contain the following parts in this exact order:

```
\section{Benchmark Problem NNN}

    Problem X.1.  [problem statement with numbered equations]

    Note X.2 (Origin of the problem).  [source, domain]

    Note X.3 (Difficulty of the problem).  [difficulty assessment — YOU GENERATE]

    Solution to Problem X.1.  [reference solution — VERBATIM TRANSLATE from GPT's answer.
        Start with "The following solution was given by ChatGPT 5.5."
        Then state the answer, then give the complete proof.]

    Rubric X.4.  [based on user's rubric, list key criteria with point allocations,
        define partial/full scoring rules, summarize with align block]

    Comparison X.5 (ChatGPT 5.5 vs. Doubao).
        [Evaluate Doubao's answer against each rubric criterion.
        First acknowledge correct reasoning, then assess gaps.
        Apply dependency-aware scoring. End with total score.]

    Review X.6.  [Diagnose root causes of Doubao's errors.
        Number of items determined by actual distinct root causes — no padding.]

\begin{thebibliography}
[references cited in the text]
\end{thebibliography}

\appendix
Appendix: Doubao Model's Answer
[VERBATIM TRANSLATE of Doubao's full answer — do NOT correct errors]
```

## Critical Rules

1. **ALL content in English.** If inputs are in Chinese, TRANSLATE everything to English.
   The Problem, Solution, and Doubao's Answer must be VERBATIM TRANSLATED —
   every equation, every step, every case preserved at full length.

2. **Numbering convention.** Problem, Note, Rubric, Comparison, Review share one counter,
   incrementing within each subsection: X.1, X.2, X.3, X.4, X.5, X.6.
   "Solution to Problem X.1" does NOT consume the counter — it references the problem number.

3. **Equation numbering.** Important equations numbered (X.Y), independent of the environment counter.

4. **Solution attribution.** Must write:
   "The following solution was given by ChatGPT 5.5."

5. **Rubric must have point values.** Extract 2-6 key criteria from the user's rubric,
   assign points summing to 100, define partial-score rules.
   Summarize with an `\begin{align}` block with `\label{eq:rubricN}`.

6. **Comparison: balanced, dependency-aware evaluation.**

   Each criterion must be evaluated using the following protocol:

   **(a) Acknowledge correct parts first.**
   Before discussing errors, identify what Doubao did correctly for this criterion:
   correct setup, valid intermediate steps, appropriate technique selection, etc.

   **(b) Apply the principle of charitable interpretation.**
   If Doubao used a different method from the reference solution, check whether the
   alternative approach is mathematically valid or could be made valid with minor repairs.
   "Absent from reference solution" ≠ "wrong." Only penalize if the approach is
   genuinely flawed or incomplete, not merely different.

   **(c) Classify error severity.** Distinguish clearly among:
   - *Omitted justification*: the step is correct but insufficiently explained;
   - *Local gap*: an error that could be repaired without changing the overall strategy;
   - *Fatal error*: an error that invalidates the logical chain and cannot be locally fixed.
   Award partial credit proportionally: omitted justification loses less than a local gap,
   which loses less than a fatal error.

   **(d) No repeated deduction for the same root cause.**
   Identify the root causes of Doubao's errors. A single root error is penalized at
   full weight ONLY in the criterion where it most directly appears. In downstream
   criteria that depend on the flawed step, note the dependency but do NOT deduct
   full points again. Instead write:
   "This criterion is affected by the error identified in criterion (K).
   Had that step been correct, Doubao's work here would merit P pts.
   Accounting for the dependency, award Q pts."
   The total deduction across all criteria for one root cause should not exceed
   what a single full-weight penalty would impose.

   **(e) Integrate user's analysis.**
   The user provides an analysis of Doubao's answer (Input 6). Use this analysis as
   an authoritative guide to identify which errors are genuine and which apparent
   differences are acceptable alternative approaches. If the user's analysis awards
   partial credit for a criterion, respect that judgment.

   Per-item format: detailed analysis + `\textbf{X~pts (out of N).}`
   End with: `\noindent\textbf{Total score:} $a+b+\cdots = T$~pts (out of 100).`

7. **Review: diagnose only genuine root causes.**
   List the distinct root causes of Doubao's failure. The number of items is determined
   by the actual number of independent root causes — typically 2-5 items.
   Do NOT pad to reach a quota. Do NOT split one root cause into multiple items.
   Do NOT fabricate failure modes for breadth.

   Each item should be 3-8 sentences. Use the diagnostic framework
   (knowledge gaps / skill gaps / workflow defects / literature connections) as a lens,
   but only when a category genuinely applies.

   Quality test: for each item, ask "Is this a genuinely distinct root cause, or is it
   a restatement or downstream consequence of another item?" If the latter, merge it.

   End with a summary paragraph.

8. **References** only include papers actually cited in the text.

9. **Appendix** contains Doubao's complete answer, verbatim translated. Do NOT correct Doubao's mathematical errors.

10. **LaTeX rules:**
    - Start with `\documentclass{article}`, end with `\end{document}`
    - Use `\noindent\textbf{Proof.}` ... `\hfill$\square$`, NOT `\begin{proof}`
    - Use `\noindent\textbf{Definition.}`, NOT `\begin{definition}`
    - NO `\title`, `\author`, `\maketitle`, `\tableofcontents`
    - NO Unicode characters: K\"onig not König
    - Add `\label{eq:...}` to important equations

## Scoring Fairness Principles

These principles govern Rules 6 and 7 and override any conflicting instruction:

- **Alternative paths are legitimate.** If Doubao's method differs from the reference
  solution but is mathematically sound (or could be made sound with minor fixes),
  it should receive credit proportional to its validity, not zero for diverging
  from the reference.

- **One root cause, one primary deduction.** Identify each independent root error.
  Assign it to the criterion where it most directly manifests. In all other criteria
  affected by the same root error, note the dependency and apply only a reduced
  secondary penalty (or none, if the criterion's own logic is otherwise correct).

- **Severity calibration.** A missing justification for a correct step is not the same
  as an incorrect step. A repairable gap is not the same as a structural collapse.
  Score accordingly.

- **User analysis is authoritative for error identification.** The user's analysis
  (Input 6) determines which errors are real. Do not invent additional errors
  beyond what the user's analysis and your own mathematical verification support.

## Workflow

1. **Read the input file** at the path specified by the system prompt.
2. Read `references/template-structure.md` for the complete structural specification.
3. Organize the 6 input sections. If Chinese, translate to English.
4. VERBATIM TRANSLATE GPT's solution as the reference answer (full length, every step).
5. Convert the user's rubric into the template format with point allocations.
6. **Before scoring, identify all root causes** from the user's analysis (Input 6)
   and your own reading of Doubao's answer. List them internally.
7. Score Doubao's answer against each rubric criterion using the balanced evaluation
   protocol (Rule 6). Apply dependency-aware deduction.
8. Write the Review section covering only the genuine root causes identified in Step 6.
9. Compile references.
10. VERBATIM TRANSLATE Doubao's answer for the appendix (preserve all errors).
11. **Write the complete `.tex` file** to the output path specified by the system prompt.
