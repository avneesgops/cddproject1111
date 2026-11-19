# AVeriTeC data

`train.json` and `dev.json` are from the official AVeriTeC repository. The project converts them into claim/evidence training rows in `../verification/` by retaining claim text, evidence question-answer pairs, source links, location metadata, and the four-way label. The fact-checker justification and verdict article are not used as model input.

- Official project and files: https://github.com/MichSchli/AVeriTeC
- Dataset page and schema: https://fever.ai/dataset/averitec.html
- Paper: Schlichtkrull, Guo, and Vlachos (2023), “AVeriTeC: A Dataset for Real-world Claim Verification with Evidence from the Web,” NeurIPS 2023.
- License: CC BY-NC 4.0. Attribute the dataset authors, link the license, and indicate modifications. It prohibits commercial use; the local use here is for a college research prototype.

The included files contain 3,068 training claims and 500 development claims. The blind test file is not included or used. The application maps AVeriTeC's `Supported`, `Refuted`, `Not Enough Evidence`, and `Conflicting Evidence/Cherry-picking` labels to the canonical four labels used by VerifyNews.

Modification note: two archived source URLs in `train.json` had `secret_password` query parameters removed before publication. Claim text and evidence content were not changed by this redaction.
