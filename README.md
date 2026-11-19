# VerifyNews AI

VerifyNews is an educational claim research prototype. It extracts candidate sentences from an article, retrieves similar previously fact-checked claims from a multilingual research dataset, and searches Wikipedia's public API for related reference pages. It does not assign a whole-article fake/true label. Neither lookup requires a paid API key.

> Related Wikipedia pages provide context, not a verdict. Search coverage is incomplete, and a missing match is **not** evidence that a claim is false. Claim model outputs are research estimates and need human review.

## Features

## Code layout

The Streamlit entry point stays in `app.py`. Supporting code lives in the `verifynews/` package: `pages.py` contains the Analyze and Casebook pages, `casebook_ui.py` renders the review workflow, `storage.py` persists cases in SQLite, `components.py` renders claim evidence, `verification.py` handles retrieval and model predictions, `news.py` loads headlines, and `config.py` holds shared paths and constants. This keeps the demo run command and the local case database in place while making each area easier to change independently.

- Paste an article or analyze an article URL, then inspect up to five candidate claims.
- Search for related Wikipedia pages for each candidate claim and show excerpts and source links.
- Choose a Wikipedia language edition for source lookup in one of the 14 languages present in the included training split.
- Search 31,373 previously fact-checked claims from 15 fact-checking sites and 14 languages; show close text matches with their original ratings, evidence excerpts, and links.
- Train a four-label claim-and-evidence baseline using X-FACT plus AVeriTeC; report separate in-domain, new-site, zero-shot, and AVeriTeC transfer metrics.
- Optionally fine-tune a multilingual XLM-R verifier locally with class-weighted training; no paid API is required.
- Compare up to three article URLs by extracting one candidate claim from each and searching for related reference pages.
- See LinearSVC and, when installed, XLM-R held-out evaluation metrics.
- Compare each available claim/evidence model's estimate for a claim when readable evidence is retrieved.
- Show current headlines from a keyless RSS feed or optional NewsAPI without treating them as fact checks.
- Save analyses in a local verification casebook with a review workflow, evidence map, activity timeline, reviewer notes, and downloadable brief.
- Run as a local Python app or a Docker container.
- GitHub Actions checks Python syntax, builds the image, starts the container, checks its health endpoint, and publishes images to GHCR on the repository's default branch.

## Run locally

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

On first run, the app trains and evaluates the claim/evidence baseline and builds the fact-check search index. It saves local artifacts under `.verifynews_cache/`, keyed to the source dataset sizes and modification times, so later app restarts can load them instead of rebuilding everything. The cache is disposable and ignored by Git; changing a dataset creates a fresh cache automatically. The old `Fake.csv` and `True.csv` article-pattern classifier is no longer loaded or shown by the site.

The X-FACT and AVeriTeC reference and evaluation data are under `datasets/`; source and citation details are in `datasets/XFACT-ATTRIBUTION.md` and `datasets/averitec/ATTRIBUTION.md`. Run `python scripts/prepare_verification_data.py` after changing source data to rebuild the normalized files in `datasets/verification/`. The four training ratings preserve the distinction between supported, refuted, mixed, and not enough evidence. AVeriTeC is licensed CC BY-NC 4.0 and is included for non-commercial educational research; see its attribution file.

The included AVeriTeC training source has two archived source URLs with their `secret_password` query parameters removed; claim and evidence content was not changed by this redaction. The data preparation script does not copy source URLs into model input.

The default claim model is a lightweight LinearSVC baseline. It uses the claim plus evidence text for training; at prediction time it receives the claim and retrieved Wikipedia extracts, which is a domain shift. Wikipedia pages are one provider, not independent corroboration, so the UI abstains instead of treating their count as proof. Similar wording in a prior fact-check is only a candidate match; the app links to the original record and never transfers its rating to a different claim automatically.

## Current headlines and Jenkins

The home page shows current headlines from a public Google News RSS feed without a key. Headlines are clearly separate from claim checks and do not create a truth rating. NewsAPI can be used optionally by storing its token as a Jenkins **Secret text** credential with ID `newsapi-key`; enable the `USE_NEWSAPI_KEY` pipeline parameter to use it. The key is read from the `X-Api-Key` request header and is never written to the feed snapshot. The top-headlines request and authentication method are documented by [NewsAPI](https://newsapi.org/docs/endpoints/top-headlines) and [NewsAPI authentication](https://newsapi.org/docs/authentication).

The root `Jenkinsfile` runs on a 15-minute schedule, checks Python syntax, fetches up to 12 headlines, and archives `datasets/current_news.json`. Create a Jenkins Pipeline job pointed at this repository and make sure its agent has Python 3. It uses the no-key RSS feed by default; the optional NewsAPI credential can be enabled with a build parameter. The generated snapshot is ignored by Git. To have the website use scheduled snapshots, deploy/copy the archived file into the running app's `datasets/current_news.json` path (or run Jenkins against the same app workspace). Otherwise set `NEWS_API_KEY` in the Streamlit server environment to use NewsAPI directly. For Docker Compose, set `NEWS_API_KEY` in the shell or a local `.env` file before `docker compose up`; do not commit `.env` or the key. Without that variable, the website uses the public RSS feed directly.

The default NewsAPI country is India (`in`) and category is `general`; Jenkins parameters can change these. API access and allowed usage depend on the NewsAPI plan and key.

## Verification casebook

After analyzing a link or pasted article, choose **Save to casebook**. Use the app's top navigation to open the separate **Casebook** page. Cases appear as compact cards grouped into status buckets: New, Assigned for review, Evidence found, Needs follow-up, and Closed. Changing an active case's status saves immediately and moves it into the matching bucket. Open an active card to see only that case's claims, evidence, reviewer notes, and activity. Closed cases remain listed but cannot be opened or reassigned directly; their only action is **Reopen case**, which returns them to Assigned for review. Retrieved evidence begins as **Unreviewed**; reviewers can label each relationship as Supports claim, Contradicts claim, Context, or Unclear / needs review. Evidence labels are separate from case workflow status. Similar X-FACT records remain references to previous claims and their original ratings are never carried over to the current claim. The timeline records case creation and later status, notes, and evidence-label changes. Cases previously marked Reviewing are migrated to Assigned for review when the app opens the casebook.

The project code currently has no license file; dataset licenses and reuse terms are separate and are listed in their attribution files.

Cases are stored locally in `data/verifynews_cases.sqlite3`, which is excluded from Git. Docker Compose uses a named volume so cases survive container rebuilds. The downloadable brief contains the case metadata, claims, model estimates, evidence excerpts and links, reviewer labels, notes, and activity history.

To fine-tune the optional multilingual XLM-R verifier locally, install the separate ML dependencies and run:

```powershell
python -m pip install -r requirements-ml.txt
python scripts/train_xlmr_verifier.py
```

This downloads the pretrained model and needs substantial disk space, RAM, and preferably a GPU. The script saves the checkpoint and reports separate held-out X-FACT in-domain, new-site, and zero-shot scores under `models/xlmr_claim_verifier/`. XLM-R is not active until that checkpoint exists. Training has not been run as part of this code change because the current environment does not have PyTorch or Transformers installed.

X-FACT contains reviewed claims with nuanced ratings, while AVeriTeC contributes real-world claims paired with evidence questions and answers. The app uses a four-way claim-and-evidence baseline for this task. X-FACT's full benchmark covers 25 languages; the included training split covers 14 languages and 15 fact-checking sites. The model is a research baseline, and zero-shot performance may be substantially lower than in-domain performance.

## Run with Docker

```powershell
docker compose up --build
```

Then open [http://localhost:8501](http://localhost:8501). To stop the app, run `docker compose down`.

The Docker image includes normalized claim/evidence data, X-FACT lookup data, and dataset attributions so the demo works without uploading them. For the GitHub Actions published image, pull `ghcr.io/OWNER/REPOSITORY:latest` and run:

```powershell
docker run --rm -p 8501:8501 ghcr.io/OWNER/REPOSITORY:latest
```

Replace `OWNER/REPOSITORY` with the GitHub account and repository name. The first push to GHCR may require setting the package visibility to public if examiners need to pull it without authentication.

## CI/CD

The workflow is at `.github/workflows/ci-cd.yml`. Pull requests and pushes build the Docker image and wait for Streamlit's health endpoint. Pushes to the default branch also publish `latest` and commit-tagged images to GitHub Container Registry using the built-in `GITHUB_TOKEN`.

## Model notes

The claim model's metrics describe its benchmark splits, not guaranteed performance on current news. Dataset construction, time period, labeling, and language can bias results. URL extraction depends on the page being publicly accessible and compatible with newspaper3k. The app abstains from a claim verdict when it lacks independent corroboration.
