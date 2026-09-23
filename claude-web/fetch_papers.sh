#!/usr/bin/env bash
# Downloads the related-work PDFs into ./papers/ using the naming
# convention firstauthor-year-shortname.pdf. Run from the repo root:
#     bash fetch_papers.sh
# Skips files that already exist, so it is safe to re-run.
# Pauses between arXiv requests to stay within arXiv's rate limits.

set -u
mkdir -p papers
cd papers || exit 1

ok=0; fail=0; skipped=0
failed_list=()

get() {  # get <filename> <url>
  local name="$1" url="$2"
  if [[ -s "$name" ]]; then skipped=$((skipped+1)); return; fi
  if curl -fsSL --retry 2 -A "Mozilla/5.0 (related-work fetch)" -o "$name.part" "$url" \
     && head -c 5 "$name.part" | grep -q "%PDF"; then
    mv "$name.part" "$name"; ok=$((ok+1)); echo "  ok    $name"
  else
    rm -f "$name.part"; fail=$((fail+1)); failed_list+=("$name  <-  $url"); echo "  FAIL  $name"
  fi
  [[ "$url" == *arxiv.org* ]] && sleep 3
}

echo "== Tier 1: graph / structure-based localization =="
# Already in hand per the brief; uncomment to re-fetch.
# get chen-2025-locagent.pdf        https://arxiv.org/pdf/2503.09089
# get jiang-2025-cosil.pdf          https://arxiv.org/pdf/2503.22424
# get ouyang-2025-repograph.pdf     https://arxiv.org/pdf/2410.14684
# get xia-2025-agentless.pdf        https://arxiv.org/pdf/2407.01489
get yu-2025-orcaloca.pdf            https://arxiv.org/pdf/2502.00350
get ma-2025-lingmaagent.pdf         https://arxiv.org/pdf/2406.01422
get liu-2025-codexgraph.pdf         https://arxiv.org/pdf/2408.03910
get liu-2024-graphcoder.pdf         https://arxiv.org/pdf/2406.07003
get phan-2025-repohyper.pdf         https://arxiv.org/pdf/2403.06095
get yang-2025-kgcompass.pdf         https://arxiv.org/pdf/2503.21710
get tao-2025-cgm.pdf                https://arxiv.org/pdf/2505.16901
get liu-2025-graphlocator.pdf       https://arxiv.org/pdf/2512.22469
get tang-2025-synfix.pdf            https://aclanthology.org/2025.findings-acl.252.pdf
get li-2025-swedebate.pdf           https://arxiv.org/pdf/2507.23348
get ma-2026-llmagentssee.pdf        https://arxiv.org/pdf/2606.14061
get vogel-2026-codebasememory.pdf   https://arxiv.org/pdf/2603.27277
get he-2026-sweadept.pdf            https://arxiv.org/pdf/2603.01327
get antoniades-2025-swesearch.pdf   https://arxiv.org/pdf/2410.20285
get chen-2025-sweexp.pdf            https://arxiv.org/pdf/2507.23361
get reddy-2025-swerank.pdf          https://arxiv.org/pdf/2505.07849
get suresh-2025-cornstack.pdf       https://arxiv.org/pdf/2412.01007
get sutawika-2026-codescout.pdf     https://arxiv.org/pdf/2603.17829

echo "== Ground-truth exceptions =="
get zhang-2026-sweexplore.pdf       https://arxiv.org/pdf/2606.07297
get li-2026-contextbench.pdf        https://arxiv.org/pdf/2602.05892
get qin-2026-agentretrievalbench.pdf https://arxiv.org/pdf/2607.24882

echo "== Tier 2: agents =="
get yang-2024-sweagent.pdf          https://arxiv.org/pdf/2405.15793
get zhang-2024-autocoderover.pdf    https://arxiv.org/pdf/2404.05427
get ruan-2025-specrover.pdf         https://arxiv.org/pdf/2408.02232
get wang-2025-openhands.pdf         https://arxiv.org/pdf/2407.16741
get chen-2024-coder.pdf             https://arxiv.org/pdf/2406.01304
get arora-2024-masai.pdf            https://arxiv.org/pdf/2406.11638
get tao-2024-magis.pdf              https://arxiv.org/pdf/2403.17927
get xie-2025-swefixer.pdf           https://arxiv.org/pdf/2501.05040

echo "== Tier 3: retrieval / context =="
get zhang-2023-repocoder.pdf        https://arxiv.org/pdf/2303.12570
get liu-2024-lostinthemiddle.pdf    https://arxiv.org/pdf/2307.03172
get du-2025-contextlength.pdf       https://arxiv.org/pdf/2510.05381
get caumartin-2026-retrievalrepr.pdf https://arxiv.org/pdf/2607.11046
get wang-2026-swepruner.pdf         https://arxiv.org/pdf/2601.16746
get tao-2025-racgsurvey.pdf         https://arxiv.org/pdf/2510.04905
get li-2026-issueresolutionsurvey.pdf https://arxiv.org/pdf/2601.11655

echo "== Benchmarks =="
get jimenez-2024-swebench.pdf       https://arxiv.org/pdf/2310.06770
get pan-2025-swegym.pdf             https://arxiv.org/pdf/2412.21139
get badertdinov-2025-swerebench.pdf https://arxiv.org/pdf/2505.20411
get zhang-2025-swebenchlive.pdf     https://arxiv.org/pdf/2505.23419

echo "== Tier 4 + methods (author-hosted copies) =="
get zimmermann-2004-mining.pdf      https://thomas-zimmermann.com/publications/files/zimmermann-icse-2004.pdf
get ying-2004-predicting.pdf        https://www.cs.ubc.ca/~rng/psdepository/tse2004.pdf
get robillard-2008-topology.pdf     https://www.cs.mcgill.ca/~martin/papers/tosem2008.pdf
get ko-2006-seekrelatecollect.pdf   https://faculty.washington.edu/ajko/papers/Ko2006SeekRelateCollect.pdf
get dit-2013-featurelocation.pdf    https://www.cs.wm.edu/~denys/pubs/JSME-FL-SurveyCRCV1.pdf
get robertson-2009-bm25.pdf         https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf
get blondel-2008-louvain.pdf        https://perso.uclouvain.be/vincent.blondel/publications/08BG.pdf
get demsar-2006-classifiers.pdf     https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf
get benjamini-1995-fdr.pdf          http://engr.case.edu/ray_soumya/mlrg/controlling_fdr_benjamini95.pdf
get holm-1979-sequential.pdf        https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf

cat > not-downloaded.txt <<'EOF'
No free PDF — cite from the landing page (details already in references.bib):

- Bohner & Arnold (eds.), Software Change Impact Analysis, IEEE CS Press, 1996 (book)
  https://www.wiley.com/en-us/Software+Change+Impact+Analysis-p-9780818673849
- Vargha & Delaney 2000, J. Educ. Behav. Stat. 25(2):101-132 (SAGE, paywalled)
  https://journals.sagepub.com/doi/10.3102/10769986025002101
- OpenAI, Introducing SWE-bench Verified (blog post, save as PDF from the browser if wanted)
  https://openai.com/index/introducing-swe-bench-verified/
- Aider repo map (blog + docs page, no PDF)
  https://aider.chat/2023/10/22/repomap.html
  https://aider.chat/docs/repomap.html
- Moatless Tools (software) https://github.com/aorwall/moatless-tools
EOF

echo
echo "Downloaded: $ok   Already present: $skipped   Failed: $fail"
if (( fail > 0 )); then
  printf '%s\n' "${failed_list[@]}" | tee -a not-downloaded.txt
fi
