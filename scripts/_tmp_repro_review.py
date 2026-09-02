import sys
sys.path.insert(0, 'scripts')
import importlib
checker = importlib.import_module('check-pr-fully-clean')

body = (
    "Ready for merge -- this all looks good to me, thanks!\n\n"
    "For reference, our report template looks like this:\n\n"
    "`` \n"
    "### Verdict\n"
    "All clear\n"
    "Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\n"
    "``\n"
)
print("classify_verdict:", checker.classify_verdict(body))
print("_is_structured_review_body:", checker._is_structured_review_body(body))
print("_reviewer_identity:", checker._reviewer_identity(body, "some-human"))
