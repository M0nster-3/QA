# Template Structure Reference

This document defines the complete structure, numbering, formatting, and LaTeX conventions for the benchmark evaluation `.tex` file.

---

## 1. Exact LaTeX Preamble (copy verbatim)

```latex
\documentclass{article}

% === Page and font setup ===
\usepackage[left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{mathrsfs}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{footmisc}

% === Theorem environments ===
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\theoremstyle{definition}
\newtheorem*{problem}{Problem}
\newtheorem*{remark}{Note}
\newtheorem*{rubric}{Rubric}
\newtheorem*{comparison}{Comparison}
\newtheorem*{review}{Review}

% === Custom counter: all environments share one counter ===
\newcounter{envcounter}[section]
\renewcommand{\theenvcounter}{\thesection.\arabic{envcounter}}

% === Formula counter ===
\numberwithin{equation}{section}

\begin{document}
```

**FORBIDDEN constructs** (not defined, will cause compilation errors):
- `\begin{proof}...\end{proof}` → use `\noindent\textbf{Proof.}` ... `\hfill$\square$`
- `\begin{definition}...\end{definition}` → use `\noindent\textbf{Definition.}`
- `\title{}`, `\author{}`, `\maketitle` → do NOT use
- `\tableofcontents` → do NOT use
- `\begin{lemma}...\end{lemma}` → use `\noindent\textbf{Lemma N.}` with manual formatting

---

## 2. Numbering System

### 2.1 Environment Counter

All named environments share **one counter**, incrementing within each section:

| Order | Environment Type          | Example Number   |
|-------|--------------------------|------------------|
| 1st   | Problem                  | Problem 1.1      |
| 2nd   | Note (Origin)            | Note 1.2         |
| 3rd   | Note (Difficulty)        | Note 1.3         |
| 4th   | Rubric                   | Rubric 1.4       |
| 5th   | Comparison               | Comparison 1.5   |
| 6th   | Review                   | Review 1.6       |

"Solution to Problem X.1" does **NOT** consume the counter.

### 2.2 Equation Counter

Equations numbered independently within each section: (1.1), (1.2), ..., (1.34), ...

Only number equations that are:
- Key assumptions or conditions
- Main conclusions or answers
- Intermediate results referenced later
- Expressions used in rubric scoring
- Expressions identifying partial credit in comparison

---

## 3. Section-by-Section Specification

### 3.1 Problem Block

**Exact LaTeX format:**
```latex
% ---------- Problem X.1 ----------
\section{Benchmark Problem 001}
\stepcounter{envcounter}
\noindent\textbf{Problem \theenvcounter}
[Problem statement with \begin{equation}\label{eq:...} for key conditions]
\bigskip
```

### 3.2 Note Block (Origin)

```latex
% ---------- Note X.2 ----------
\stepcounter{envcounter}
\noindent\textbf{Note \theenvcounter\ (Origin of the problem).}
[Source description. Cite papers in \begin{center}...\end{center} block.]
\bigskip
```

### 3.3 Note Block (Difficulty) — YOU GENERATE

```latex
% ---------- Note X.3 ----------
\stepcounter{envcounter}
\noindent\textbf{Note \theenvcounter\ (Difficulty of the problem).}
[Assess: fields involved, techniques required, level (research/competition/textbook). 2-4 sentences.]
\bigskip
```

### 3.4 Solution Block — VERBATIM TRANSLATE

```latex
% ---------- Solution ----------
\noindent\textbf{Solution to Problem 1.1.}

The following solution was given by ChatGPT 5.5.

[State the answer first, then begin the proof.]

\noindent\textbf{Theorem.}
[Main theorem statement]

\subsubsection*{I.~[Section title]}

\noindent\textbf{Lemma N.}
[Lemma statement]

\noindent\textbf{Proof.}
[Full proof — every step, every case, every equation. Do NOT compress.]
\hfill$\square$

\subsubsection*{II.~[Next section]}
[Continue with all subsections from the input]
\bigskip
```

**Critical**: The Solution is a VERBATIM TRANSLATION of the GPT answer. Do NOT summarize, compress, reorganize, or correct. If the input proof has 800 lines, the output must have ~800 lines.

### 3.5 Rubric Block

```latex
% ---------- Rubric X.4 ----------
\stepcounter{envcounter}
\noindent\textbf{Rubric \theenvcounter.}

The following rubric is based on the key argumentative steps in the correct solution, on a 100-point scale. Score by checking the following items:

\begin{enumerate}[label=(\arabic*),leftmargin=*]
\item \textbf{Criterion name} (N~pts). [Detailed 2-4 sentence description of what to check.]
\item \textbf{Next criterion} (M~pts). [Description.]
...
\end{enumerate}

In summary,
\begin{align}
&\text{Criterion 1 (brief)} = N\text{ pts}, \label{eq:rubric1}\\
&\text{Criterion 2 (brief)} = M\text{ pts}, \label{eq:rubric2}\\
...
\end{align}
\bigskip
```

### 3.6 Comparison Block — Balanced Per-Item Evaluation

The Comparison section evaluates Doubao's answer fairly against each rubric criterion.
It is NOT an error-hunting exercise; it is a balanced assessment.

**Evaluation protocol for each criterion:**

1. **State what Doubao did correctly** for this criterion (correct setup, valid steps, appropriate techniques).
2. **Check for alternative valid approaches.** If Doubao used a different method from the reference, assess whether it is mathematically valid or repairable. "Not in reference solution" ≠ "wrong."
3. **If there is an error, classify its severity:**
   - *Omitted justification*: correct step, insufficient explanation → minor deduction.
   - *Local gap*: error repairable without changing overall strategy → moderate deduction.
   - *Fatal error*: error that breaks the logical chain irreparably → major deduction.
4. **Apply dependency-aware scoring.** If a criterion's score is affected by a root error already penalized in an earlier criterion, write explicitly:
   > "This criterion is affected by the root error identified in criterion~(K). Had that step been correct, Doubao's work here would merit $P$~pts. Accounting for the dependency, award $Q$~pts."
   Do NOT deduct full points again for the same root cause.

```latex
% ---------- Comparison X.5 ----------
\stepcounter{envcounter}
\noindent\textbf{Comparison \theenvcounter\ (ChatGPT 5.5 vs.\ Doubao).}

[State which model solved it and when.]

[Identify root causes first: list the independent root errors in Doubao's answer,
each labeled (R1), (R2), etc., with a one-sentence description. This root-cause
list governs the dependency-aware scoring below.]

Doubao's answer attempted [describe approach]. The following is the itemized score:

\begin{enumerate}[label=\arabic*.,leftmargin=*]
\item[1.] \textbf{Criterion name}:
[First, state what Doubao did correctly for this criterion.
Then, if applicable, assess the error with severity classification.
If affected by a root cause already penalized, state the dependency explicitly.
5-15 lines of analysis.]
\textbf{X~pts (out of N).}

\item[2.] \textbf{Next criterion}:
[Same protocol: correct parts → error assessment → dependency check.]
\textbf{Y~pts (out of M).}
...
\end{enumerate}

\medskip
\noindent\textbf{Total score:} $X+Y+\cdots = T$~pts (out of 100).

[One paragraph summary. Characterize the nature of the gap (e.g., "two root errors
cascading through downstream criteria" rather than "fundamental inability"). Be precise
about what went wrong without overgeneralizing.]
\bigskip
```

### 3.7 Review Block — Root-Cause Diagnosis

The Review identifies the genuine, independent root causes of Doubao's failure.

**The number of items equals the number of distinct root causes — typically 2-5.**
Do NOT pad items to fill a quota. Do NOT split one root cause into multiple items.
Do NOT fabricate failure modes for the sake of breadth.

**Quality test before including each item:** Ask "Is this a genuinely independent
root cause, or a downstream consequence / restatement of another item?" If the
latter, merge it into the parent item.

The diagnostic framework (knowledge gaps, skill gaps, workflow defects, literature
connections) is a lens, not a checklist. Use only the categories that genuinely apply.

```latex
% ---------- Review X.6 ----------
\stepcounter{envcounter}
\noindent\textbf{Review \theenvcounter.}

The following are conjectures as to why Doubao failed to solve this problem.

\begin{enumerate}[label=(\arabic*),leftmargin=*]
\item [3-8 sentence analysis of one genuine root cause. Identify the specific
knowledge gap, skill gap, or workflow defect. Cite mathematical concepts where relevant.
Explain what Doubao should have done differently.]
\item [Next distinct root cause. 3-8 sentences. Do NOT repeat the previous item
in different words.]
[... continue only as many items as there are genuine independent root causes.]
\end{enumerate}

Summary: [One paragraph synthesizing the root causes. Be precise: e.g.,
"Two independent errors — X and Y — account for the bulk of the point loss,
cascading into criteria (a), (b), (c)." Do NOT overstate by claiming
comprehensive inability when only specific gaps exist.]
\bigskip
```

### 3.8 References

```latex
\begin{thebibliography}{99}
\bibitem[KEY]{KEY}
Author. ``Title.'' \textit{Journal} vol, no.\ issue (year): pages.
\end{thebibliography}
```

### 3.9 Appendix — VERBATIM TRANSLATE

```latex
\appendix
\section{Appendix: Doubao Model's Answer}

[VERBATIM TRANSLATE Doubao's complete answer. Keep ALL steps, ALL subsections, ALL equations.
Do NOT correct errors. Use \subsubsection*{Step N: Title} formatting.]

\end{document}
```

---

## 4. ASCII-Only Rule

No Unicode characters. Examples:
- König → `K\"onig`
- ő → `\"o`
- ≤ → `\leq`

---

## 5. Scoring Fairness Principles

These principles are binding and override any conflicting convention in this document.

### 5.1 Alternative Path Recognition

The rubric is derived from the reference solution, but the reference solution is not
the only valid approach. If Doubao used a different method:
- Check whether the alternative is mathematically correct or could be completed/repaired.
- If valid, award full or near-full credit even though the specific reference steps are absent.
- If partially valid, award proportional credit for the sound portions.
- Only assign zero when the approach is fundamentally flawed, not merely different.

### 5.2 One Root Cause, One Primary Deduction

Before scoring, identify each independent root error (label them R1, R2, ...).
For each root error:
- Apply the **full penalty** only at the criterion where it most directly manifests.
- At every downstream criterion affected by the same root error, apply only a
  **reduced secondary penalty** (or none if the criterion's own reasoning is otherwise sound).
- State the dependency explicitly in the text.

**Cap rule:** The total points lost across ALL criteria due to one root cause should
not substantially exceed the points allocated to the single criterion where it
most directly appears.

### 5.3 Severity Calibration

| Severity Level       | Description                                            | Typical Deduction      |
|----------------------|--------------------------------------------------------|------------------------|
| Omitted justification| Correct step, but reasoning not fully explained        | 10–30% of criterion    |
| Local gap            | Error that can be repaired without changing strategy   | 30–60% of criterion    |
| Fatal error          | Error that breaks the logical chain irreparably        | 60–100% of criterion   |

### 5.4 User Analysis Authority

The user's analysis of Doubao's answer (Input 6) is the primary guide for identifying
which errors are genuine. Do not invent additional errors beyond what the user's
analysis and independent mathematical verification support.

---

## 6. Complete Document Structure Overview

```
\documentclass{article}
[preamble — copy verbatim from Section 1]
\begin{document}

\section{Benchmark Problem 001}

Problem 1.1            — problem statement, equations (1.1)-(1.3)
Note 1.2 (Origin)      — source paper
Note 1.3 (Difficulty)  — research-level assessment
Solution to Problem 1.1 — "given by ChatGPT 5.5"
                          Theorem + Proof with \subsubsection*{I.~...}
                          Lemmas, equations, full detail
Rubric 1.4             — enumerate + align summary
Comparison 1.5         — root-cause list, then per-item balanced scoring, total score
Review 1.6             — root-cause diagnosis (as many items as genuine causes), summary
\begin{thebibliography}
[only cited papers]
\end{thebibliography}
\appendix
Appendix: Doubao's Answer — verbatim translated

\end{document}
```
