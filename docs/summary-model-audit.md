# Summary model audit

Audited: 2026-11-01. This report contains aggregate counts and non-secret identifiers only.

## Result

One trained artifact exists: `backend/models/model.pkl` (962 bytes). It is a joblib bundle containing a scikit-learn `LinearRegression` numeric views predictor. It is not a text-generating feedback model and is disabled for Summary feedback. No tuned-model endpoint, hosted feedback endpoint, model bucket/object path, notebook, or additional model artifact was found in the working tree or full git history.

The artifact was introduced in commit `01923fc5f006424e6d26ffe4d82c0b0a7e79727d` on 2026-03-30 and last changed in `a41d3176f1b5357a15146cfee15b944cf47b58a1` on 2026-10-25. It was **not deleted**; consequently there is no deletion commit or restore step. The retired milestone/analysis implementation, not this artifact, was deleted by `151612eebb2d3ea37ec52e9095d8d4fdaf1dbd90` on 2026-10-30.

## Candidate detail

- Location: `backend/models/model.pkl`; training source: `backend/models/train_model.py`.
- Type/output: numeric linear regression; one predicted view-count float. It cannot produce feedback text without turning a prohibited prediction into a template input.
- Input schema: encoded `platform`, encoded `contentType`, `captionLength`, and `postingHour`. Earlier history also included `hashtagsCount`; that feature was removed in `a41d317`.
- Training data: 240 deterministic synthetic rows generated in code from three platform labels, four content-type labels, five caption lengths, and four posting hours, plus seeded noise. It was trained on no creator posts, no author account, and no private dataset.
- Runtime: CPU-only scikit-learn/joblib; artifact size is under 1 KB and memory needs are negligible. `scikit-learn==1.8.0` and `joblib` are already in backend requirements. `Dockerfile.production` copies the artifact into the OCI image, so it can technically run in the current linux/arm64 deployment.
- Hosting/storage: local image artifact only. The only configured OCI bucket identifier is the generic media `OCI_BUCKET_NAME`; no model object name/path or tuned endpoint identifier exists.
- License: scikit-learn and joblib use BSD-style licenses, but the repository root does not declare a license for this project-created artifact. The mobile subproject license does not establish an artifact license.

## Acceptance decision

The trained provider fails acceptance check (ii): it is a numeric predicted-views model. It is never enabled, never receives Summary facts, and its numeric output is never shown or fed into feedback. Checks (i) and (iii) would otherwise pass (deployable and synthetic/non-tenant training); check (iv) is inapplicable because the provider is disabled before generation. `FEEDBACK_TRAINED_ENABLED=false` remains the documented safe setting.

`FEEDBACK_PROVIDER=auto` therefore selects Gemini when configured and healthy, then the deterministic fact templates. Explicit `trained` configuration still falls through immediately because this artifact is ineligible.

## Search coverage

The audit covered current and deleted `.pkl`, `.joblib`, `.pt`, `.pth`, `.onnx`, `.safetensors`, `.gguf`, `.h5`, `.bin`, notebooks and dataset extensions; training/dependency references; prediction and viral-score pickaxes; Docker/Compose copy and volume declarations; OCI storage identifiers; configured model identifiers; and tuned/hosted endpoint references. The current tree contains only the single `.pkl` artifact. Legacy `viral_score` and view-prediction code remains in old prediction surfaces, but it is not used by the new Summary path.
