# M6 note: what was produced, the checks, the deviations

*14 Nov 2026. Plan: [`M6_plan.md`](M6_plan.md), approved by the author with its three defaults before anything
was produced. No data file was opened for a new computation and nothing new was decoded: every number of the
report, the graphical abstract and the slides comes from result files, logs and reports that were already
committed.*

## Produced

| | File | Content |
|---|---|---|
| Report | [`REPORT.md`](../../REPORT.md) | Results first; about 2 300 words, 6 figures |
| Graphical abstract | [`figures/graphical_abstract.png`](../../figures/graphical_abstract.png) | Drawn by `scripts/m6_graphical_abstract.py` from `results/final/lockbox/` |
| Presentation | [`docs/presentation.pptx`](../presentation.pptx), [`docs/presentation.pdf`](../presentation.pdf) | 8 slides, editable (theme, layouts, two native charts, speaker notes) |
| Repository | `README.md`, `CITATION.cff`, `run_all.sh` | Abstract and tested results first, then reproduce, then the milestones in order |

Defaults applied: PowerPoint file with a PDF copy (Q1); author line with name and repository link, no
affiliation (Q2); the README keeps the only full statement on AI assistance, and the report and the last slide
carry one line that points to it (Q3).

## Checks and their outcome

1. **Numbers.** Every number of `REPORT.md` was compared with `logs/final_lockbox.log`,
   `logs/final_summary.log` and the milestone reports. Each of the 50 decimal numbers on the slides occurs in
   the report, the logs or the milestone reports. The graphical abstract reads its numbers from the result
   files.
2. **Slides.** The file passes the validation of its format; every slide was rendered and looked at.
3. **Fresh clone.** The public repository was cloned into an empty folder at commit `982145d`. There:
   - the 71 unit tests pass;
   - M4 (decisions, summary, figures) and the final steps (rehearsal, template and networks for the lockbox
     people, **reproduction** of the lockbox numbers, figures, descriptive summary, graphical abstract) were
     recomputed with new caches;
   - **no tracked file changed:** result tables, figures and checksums are identical to the committed ones,
     byte for byte, and so are the summaries. The lockbox was not opened a second time.
   - Limits of this check: the libraries were not installed into a new environment (the PyTorch download is
     several GB); the installed versions are those of `requirements.txt`. The 12 networks of the final steps
     were loaded from the repository, not trained again. M0 to M3 were not run again here; they were re-run
     clean at their own milestones.
4. **Repository.** No data file is tracked. No personal e-mail address is in the files or in the commit
   metadata (the commits carry GitHub's no-reply address). Both licences are present. The 18 Markdown files
   have no broken local link.

## Deviations and corrections

| | Point | Why |
|---|---|---|
| D1 | Figure `figures/m4/02_people.png` was redrawn: larger canvas, shorter title, one label reworded. The data are the same. | Its title and note were cut off and two labels overlapped. Found when the figure was placed in the report. |
| D2 | The program that builds the slides is not in the repository. | It uses a JavaScript library and a helper that is not part of this project. The slides are an editable file, and their numbers were checked as above. |
| D3 | After approval, one sentence of the plan about uses of the project outside the repository was replaced by a neutral one, and two words were changed. | It did not belong in a public document. Nothing of M6 depends on it. |
| D4 | The report has about 2 300 words (planned: about 2 500). | Nothing was left out. |

## Left to the author

- Push the tag `pre-lockbox` (commit `6006614`); tags cannot be pushed from the machine used for the analysis.
- Check the split of the name in `CITATION.cff` (family names "Almuhammad Alali", given name "Salman").
- Repository description and topics on GitHub.

## Not done, by decision

M5 (real-time replay) and H4 (graph-based denoising). Both are stated as not done in the report, in its limits
and in its last section.
