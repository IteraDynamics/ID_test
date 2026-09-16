# Replacement sample access — 2026-09-16

## Decision update

**Benzinga direct is the first sample inquiry; no purchase recommendation yet.**
This updates the vendor ordering in EARNINGS_SOURCE_DECISION_20260916.md, not the
strategy or the decision to replace the calendar.

Wall Street Horizon's [contact page](https://www.wallstreethorizon.com/contact-us)
states that historical data is offered with institutional forward-data subscriptions
or an eligible academic license, not individual/personal research. It also restricts
AI/ML training and dataset licensing outside formal academic licensing. Itera's
eligibility, intended AI-assisted handling and required rights have not been
established. Do not assume that a company name establishes institutional eligibility.
No form was submitted and no representation of eligibility was made.

Benzinga's [direct earnings product](https://www.benzinga.com/apis/cloud-product/corporate-earnings/)
lists an ISIN field and history from 2012. The Massive distribution documents a
different historical start (2010-04-30) and a different schema. Neither statement
proves complete coverage or historical accuracy. Direct-feed ISIN availability is
useful but does not prove historical validity or issuer-to-price mapping. Its time
field and EST convention require clarification, especially scheduled versus actual
release and daylight saving. Last-updated metadata cannot establish when a fact
was first public. These are questions for a real sample, not reasons to assume a
vendor-wide failure.

The inspected public pages did not expose a downloadable historical sample covering
our cases. Wall Street Horizon directs trial requests to a form; Benzinga directs
users to contact/get-started access. Massive's documented example is illustrative,
not a retrieved historical sample, and its live query requires account/API access.
No credentials were supplied for this task. No vendor was contacted or paid.

## Prepared request

Recipient route: Benzinga's [official contact form](https://www.benzinga.com/apis/cloud-product/corporate-earnings/)
(via Contact Us / Try it out). Draft only; not submitted.

Subject: Historical earnings sample and timestamp definitions — Itera Dynamics

Hello,

I am evaluating historical US equity earnings data for Itera Dynamics' internal
systematic strategy research. Before purchasing a subscription, could you provide
a small evaluation extract for the 30 cases in the attached CSV, a data dictionary,
and the relevant licensing and pricing options?

The ticker/date pairs are lookup leads from a dataset we are replacing, not
assertions of the correct release date or security. Please preserve each case ID,
return explicit no-coverage or ambiguous-identity results, and include relevant
preliminary and final announcements within the lookup windows. Please use your
native format; there is no need to conform to a custom schema.

We particularly need to establish:

1. Whether historical release times are observed actual publication times,
   scheduled times, vendor receipt times, or reconstructed values; how these are
   distinguished; and the timezone/daylight-saving convention. A reliably observed
   before-open/after-close session can suffice when exact time is unavailable.
2. Whether stable issuer/security IDs, historical ticker validity, source references,
   fiscal periods, and preliminary/final relationships are available. Please explain
   ambiguous cases such as ECHO, BBT and DD rather than silently substituting a
   successor. An ISIN in today's record is not necessarily its historical identifier.
3. Whether corrected records and historical versions are available, and whether
   the sample represents today's corrected history or information available then.
   We are initially studying price reactions; consensus-estimate history is not
   needed for this first test.
4. Coverage of delisted securities, minimum subscription/commitment, sample access,
   and the rights to retain extracts and derived research after subscription expiry.
   Please also clarify whether internal analysis with an externally hosted AI
   assistant is permitted, and any restrictions on submitting sample records to it.
   Model training is not part of this initial test.

If some fields are unavailable, please identify the omissions. Please do not
initiate a paid subscription. We would evaluate the sample before any purchase.

Thank you,
Drew
Itera Dynamics

## Attachment and evaluation boundary

Attach [the 30-case request CSV](evidence/earnings_vendor_sample_request_20260916.csv).
The -30/+7 calendar-day lookup windows allow nearby/preliminary releases to be
found; they are not corrected dates or trading windows. Vendor ambiguity and
no-coverage responses remain in the denominator. Source records should be kept
private under the applicable terms; do not commit licensed extracts to GitHub.

After access, reconcile native rows to all 30 case IDs. Separate actual sessions
from schedules, validate identity on the known problem cases, and record every
omission before deciding whether to acquire broader history. Daily price/action
validation remains a separate dependency. Do not build a backtest or fit a model
from this small, inspected acceptance sample.

No new local run is required. Progress now requires a vendor reply or authorized
existing account access. The prepared draft and attachment make that step concrete;
they do not claim that a sample has been acquired.
