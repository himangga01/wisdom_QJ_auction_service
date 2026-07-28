class CrawlError(RuntimeError):
    code = "crawl_failed"
    run_status = "failed"


class BlockedCrawlError(CrawlError):
    code = "access_blocked"
    run_status = "blocked"


class LoginRequiredError(BlockedCrawlError):
    code = "login_required"


class CaptchaDetectedError(BlockedCrawlError):
    code = "captcha_detected"


class ComplexNotFoundError(CrawlError):
    code = "complex_not_found"


class AmbiguousSourceError(CrawlError):
    code = "ambiguous_source"


class SelectorMismatchError(CrawlError):
    code = "selector_mismatch"


class IncompleteListingCollectionError(CrawlError):
    code = "incomplete_listing_collection"


class BrowserUnavailableError(CrawlError):
    code = "browser_unavailable"


class BrowserDisconnectedError(CrawlError):
    code = "browser_disconnected"
