# Annotation Guidelines — GWRHelp Intent Classification

Taxonomy version:   **1**  
Taxonomy SHA-256:   `7a05e4af68a50981a3d38264b1aad8a4146fc90a342bb9804bcb5cb5148fe679`  
Evaluation unit:    the first inbound customer message of a GWRHelp thread  
Frozen golden set:  198 examples (59 dev, 139 test)  
Golden set SHA-256: `acde341dc09e85ae433d484ed8d38d4f388c0539c5523f861b6d1df36ba54817`  

**Sampling:** coverage-oriented (natural + targeted rare-intent supplement), not prevalence-representative. The `_source` field distinguishes the two slices.

---

## Assigning an intent

Every message receives exactly one `true_intent` from the frozen taxonomy. Suggested labels are scaffolding only; the human confirms or corrects every row.

## Confidence vs intent

These are **orthogonal**. `confidence` describes how sure YOU are. `true_intent` is the actual class.

**`confidence` values:**

- **high** — clear-cut, no hesitation.
- **medium** — one reasonable alternative is plausible.
- **low** — genuinely uncertain, **but you still believe one intent is more likely**.

**`ambiguous` is a `true_intent` value, not a confidence level.** Use it only when two intents are genuinely equally plausible. If you can prefer one, use that one with `confidence=low`.

## Intent definitions

### `delay_compensation`

Customer references a delayed journey or missed connection and asks how to claim compensation, typically under the Delay Repay scheme.

**Include when:**
- The message names a specific delayed service or journey, AND
- Asks how to claim, whether they qualify, or follows up on a claim.

**Exclude when:**
- The customer asks for a refund on an unused or cancelled ticket (use refund_request).
- The customer reports a live cancellation with no compensation ask (use service_disruption).

**Examples:**
- how late does my train need to be, before I can claim compensation
- can I get a delay repay
- how can I claim compensation for delayed 20:00 London to Bristol
- please advise on how I claim compensation without still having the ticket
- I need to follow up on delay repay

### `refund_request`

Customer asks for a refund or money back on a ticket, typically because the journey was unused, the service was cancelled, or the ticket became unusable.

**Include when:**
- Explicit ask for a refund, money back, or reimbursement on a ticket.

**Exclude when:**
- Asks for delay compensation instead of a refund (use delay_compensation).
- Asks about compensation on a season ticket without a refund ask (use delay_compensation).

**Examples:**
- can I get a refund on my ticket for saturday
- refund pls
- you canceled the 10:42 train can I have my money back please
- Can I get full refund on advance tickets due to engineering works
- waiting for a refund since May, will I get it before Christmas

### `booking_issue`

Problem with booking, changing, or paying for a ticket on the GWR website or app — website errors, payment failures, fare release timing, or booking flow problems.

**Include when:**
- Website or app fault during booking, payment, or account use.
- Question about when fares or tickets will be released for sale.

**Exclude when:**
- Post-booking refund (use refund_request).
- Seat reservation on an already-purchased ticket (use seat_reservation).

**Examples:**
- your website says no advanced fares are showing
- is your website down or having issues
- the booking form isn't working so can't select dates
- the website won't let me pay for a sleeper cabin
- when will London-Cornwall xmas tickets be released

### `timetable_info`

Request for schedule, platform, route, or general service information — including next-train queries and timetable publication timing.

**Include when:**
- Asks what time a train runs, which platform, or the next train on a route.
- Asks when a new or seasonal timetable will be available.

**Exclude when:**
- Reports a live disruption on a specific service (use service_disruption).
- Asks about fare release dates (use booking_issue).

**Examples:**
- what is the next train to Southall after the 16:57
- which platform will the train go from Reading to Gatwick
- when will the Christmas 2017 timetable be available
- do you have a timetable for the new trains
- what time does the 9.13 from Paddington arrive into Cardiff

### `service_disruption`

Report or query about a live disruption: cancellations, strikes, engineering works, or a route with no trains running now.

**Include when:**
- Cancellation or no-service report for a current or imminent journey.

**Exclude when:**
- Retrospective compensation claim for a completed journey (use delay_compensation).
- Generic 'the service is always late' complaint without a specific service (use on_board_issue or delay_compensation).

**Examples:**
- why is 7:34 from Didcot to Paddington cancelled - AGAIN
- 0503 train from Carmarthen to Manchester Piccadilly cancelled
- no trains from Cholsey to Paddington for nearly an hour now
- is the 13.41 from Reading to Sheffield cancelled
- why was the 7:21 from St Austell to Truro cancelled

### `seat_reservation`

Questions or problems about seat reservations, coach allocation, or the physical presence of a reserved seat or coach on the train.

**Include when:**
- Asks to reserve a seat, or reports a reservation that didn't work.
- Reports a reserved coach missing from the actual train.

**Exclude when:**
- Complaint about overcrowding without a reservation problem (use on_board_issue).
- Booking-flow error on the website (use booking_issue).

**Examples:**
- can I reserve a seat on the 0900 departure from Brighton
- reserved seat was taken, who do I speak to
- coach B is missing from the 9:45 to Bristol Parkway
- reserved seats in coach H but that coach does not exist
- my seat reservation didn't go through for tomorrow

### `lost_property`

Report of an item left on a train or at a station, or query about recovering an item via lost property.

**Include when:**
- Item left behind on a specific service or at a station.

**Exclude when:**
- Theft report (escalates separately).
- Season ticket lost / misplaced (use booking_issue or refund_request depending on the ask).

**Examples:**
- left my iphone on the 22:35 from Ealing Broadway
- I've left my suitcase on the 17:45 Pad to Swansea train
- lost a Nikon camera between St Austell and Penryn
- forgot my red suitcase on the train to Exeter
- left a bag on the 2341 from Ealing to Maidenhead

### `on_board_issue`

Complaints about conditions or staff behaviour on a train — cleanliness, temperature, overcrowding, toilet condition, luggage space, or staff conduct.

**Include when:**
- Complaint about the physical onboard environment or staff conduct.

**Exclude when:**
- Delay-related complaints (use delay_compensation).
- Reserved seats or coaches missing (use seat_reservation).

**Examples:**
- everyones standing crammed in the aisles
- standing room only on the 19:15 to Swansea
- paid £40 to be next to a flooded toilet
- packed train, rammed, overcrowded, stressful
- short train, only two carriages on the PAD to MAI

### `praise_or_chatter`

Non-actionable messages: praise, thanks, enthusiast posts, retweets, or casual mentions with no request for action.

**Include when:**
- Genuine compliment, thanks, or enthusiast post with no request.

**Exclude when:**
- Sarcastic 'thanks' embedded in a complaint (assign to the complaint's intent).
- Any message containing a request, question, or complaint.

**Examples:**
- fantastic service from Mark on the ticket desk
- amazing staff at Oxford, thank you
- big thanks to all the helpful GWRHelp staff
- thank you for the chocolate whilst we wait
- thanks to the cheery guard who brightened the journey

### `other`

No defined intent fits.

**Include when:**
- Message does not match any defined intent.

**Exclude when:**
- Any defined intent applies clearly.

**Examples:**
- love your new livery
- do you sponsor local sports clubs

### `ambiguous`

Two or more intents fit equally well.

**Include when:**
- Multiple intents apply with equal confidence.

**Exclude when:**
- A single intent dominates.

**Examples:**
- train was late and the toilet was broken, want a refund and to complain

---

## Tie-break rules

- **`delay_compensation` vs `refund_request`** — specific delay + compensation ask → `delay_compensation`. Money-back without Delay Repay mention → `refund_request`. Both present → dominant ask (usually last explicit request).
- **`delay_compensation` vs `service_disruption`** — live/current disruption → `service_disruption`. Retrospective delay with compensation ask → `delay_compensation`.
- **`on_board_issue` vs `seat_reservation`** — conditions/complaints → `on_board_issue`. Specific seat/coach reservation as subject → `seat_reservation`.
- **`on_board_issue` vs `service_disruption`** — cancellation topic → `service_disruption`. Onboard conditions on a running train → `on_board_issue`.
- **`booking_issue` vs `refund_request`** — problem during booking → `booking_issue`. Post-purchase money-back ask → `refund_request`.
- **`lost_property` vs `on_board_issue`** — item left on train/station → `lost_property`. Condition complaint → `on_board_issue`.

## `other` and `ambiguous`

**`other`** — station facilities, generic rants, brand commentary, no customer problem. Assign `other` rather than force a fit.

**`ambiguous`** — only when two intents are genuinely equally plausible. It is a label, not a hedge.

## Provenance and evaluation rules

This golden set was built in `notebooks/03_golden_set.ipynb` on top of the frozen taxonomy. Its labels are human-verified and independent from the rule-based labels in `runs/taxonomy/coverage_labeling_sheet.csv`. Reuse of the coverage set as a golden set is prohibited by the handoff contract in `02_taxonomy.ipynb`.

**Test lock:** the 139-example test split is for final reported metrics only. It must not be used for classifier, prompt, retrieval, or escalation-rule tuning.

**Metric priority:** macro F1 is primary (coverage-oriented sampling). Per-intent precision / recall / F1 and confusion matrix are reported. Accuracy is secondary and must be interpreted with sampling in mind.

## Split constraints

The dev/test split fell back to a random (non-stratified) split because
`ambiguous` has a single example — below the stratified minimum of 2.
Consequence:

- `ambiguous` appears **only in the test split**, not in dev
- Every other intent is present in both splits
- Downstream metrics for `ambiguous` are computed on test only and
  should be interpreted as a single-example result

## Annotation pool minima

- `MIN_PER_OPERATIONAL = 8` (was 12) — `lost_property` has only 8 examples
- `MIN_AMBIGUOUS = 1` (was 4) — corpus contains a single genuinely ambiguous message

These minima were lowered to match the annotation pool. No examples were
synthesized to meet the original thresholds.