"""Three synthetic firms of different shape. Each arrives the way a real client does:
as exports from the systems it happens to run, with those systems' own identifiers."""
from . import distributor, fieldservice, retail  # noqa: E402

FIRMS = {
    retail.SLUG: (retail.build, retail.extension, retail.definitions),
    fieldservice.SLUG: (fieldservice.build, fieldservice.extension, fieldservice.definitions),
    distributor.SLUG: (distributor.build, distributor.extension, distributor.definitions),
}
