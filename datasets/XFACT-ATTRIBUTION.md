# X-FACT claim reference data

`xfact_claims.csv` is a reduced local copy of the official X-FACT `train.all.tsv` split, retaining each claim, its original fact-check rating, language, fact-checking site, five evidence excerpts, five evidence links, and dates. `xfact_dev.csv`, `xfact_test.csv`, `xfact_ood.csv`, and `xfact_zeroshot.csv` preserve the corresponding official splits for validation and evaluation.

- Upstream data and project: https://github.com/utahnlp/x-fact
- Dataset access: https://huggingface.co/datasets/utahnlp/x-fact
- Paper: Gupta and Srikumar (2021), “X-FACT: A New Benchmark Dataset for Multilingual Fact Checking,” ACL-IJCNLP 2021, https://aclanthology.org/2021.acl-short.86/
- Upstream repository license: MIT. The original ratings, evidence excerpts, and links retain their source attribution; see each row's source site and link.
- Citation: Ashim Gupta and Vivek Srikumar. 2021. X-FACT: A New Benchmark Dataset for Multilingual Fact Checking. In Proceedings of ACL-IJCNLP 2021, pages 675–682.

The local training split has 31,373 records across 14 languages and 15 fact-checking sites. The included in-domain test split has 3,826 records across 13 languages; the out-of-domain split has 2,138 records across 5 languages; the zero-shot split has 3,381 records across 12 languages. X-FACT as a whole covers 25 languages; the zero-shot split evaluates languages absent from training. The app uses X-FACT to retrieve similar reviewed claims and their attributed labels/evidence. A normalized copy is combined with AVeriTeC for claim/evidence model training; the original nuanced labels are mapped into four cautious outcome groups as documented in `scripts/prepare_verification_data.py`.
