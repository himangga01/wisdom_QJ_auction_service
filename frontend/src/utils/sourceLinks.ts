interface ApartmentLinkContext {
  sourceId?: string
  runId?: string
  compareRunId?: string
  focusListingId?: string
}

interface ListingLinkContext {
  sourceId?: string
  runId?: string
}

function appendContext(
  path: string,
  context: ApartmentLinkContext,
): string {
  const params = new URLSearchParams()
  if (context.sourceId) params.set('sourceId', context.sourceId)
  if (context.runId) params.set('runId', context.runId)
  if (context.compareRunId) params.set('compareRunId', context.compareRunId)
  if (context.focusListingId) {
    params.set('focusListingId', context.focusListingId)
  }
  const query = params.toString()
  return query ? `${path}?${query}` : path
}

export function apartmentHref(
  complexId: string,
  context: ApartmentLinkContext = {},
): string {
  return appendContext(
    `/apartments/${encodeURIComponent(complexId)}`,
    context,
  )
}

export function listingHref(
  complexId: string,
  listingId: string,
  context: ListingLinkContext = {},
): string {
  return appendContext(
    `/apartments/${encodeURIComponent(complexId)}/listings/${encodeURIComponent(listingId)}`,
    context,
  )
}
