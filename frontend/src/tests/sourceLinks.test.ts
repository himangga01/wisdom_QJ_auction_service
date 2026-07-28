import { describe, expect, it } from 'vitest'
import { apartmentHref, listingHref } from '../utils/sourceLinks'

describe('source-scoped links', () => {
  it('keeps source and comparison context in an apartment URL', () => {
    expect(apartmentHref('12345', {
      sourceId: 'source-1',
      runId: 'run-2',
      compareRunId: 'run-1',
      focusListingId: 'listing-9',
    })).toBe(
      '/apartments/12345?sourceId=source-1&runId=run-2&compareRunId=run-1&focusListingId=listing-9',
    )
  })

  it('keeps source and run context in a listing URL', () => {
    expect(listingHref('12345', 'listing-9', {
      sourceId: 'source-1',
      runId: 'run-2',
    })).toBe(
      '/apartments/12345/listings/listing-9?sourceId=source-1&runId=run-2',
    )
  })
})
