from app.core.config import get_settings
from app.services.analysis_service import (
    CeleryCrawlTaskDispatcher,
    CrawlTaskDispatcher,
)

from .local_dispatcher import (
    LocalCrawlTaskDispatcher,
    get_local_dispatcher,
    shutdown_local_dispatcher,
)
from .local_locks import (
    LocalSourceLock,
    LocalSourceLockManager,
    get_local_source_lock_manager,
)


def get_crawl_dispatcher() -> CrawlTaskDispatcher:
    if get_settings().is_local:
        return get_local_dispatcher()
    return CeleryCrawlTaskDispatcher()


__all__ = [
    "LocalCrawlTaskDispatcher",
    "LocalSourceLock",
    "LocalSourceLockManager",
    "get_crawl_dispatcher",
    "get_local_dispatcher",
    "get_local_source_lock_manager",
    "shutdown_local_dispatcher",
]
