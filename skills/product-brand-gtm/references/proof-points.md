# Proof Points

Customer outcomes, benchmarks, logos, and scale facts that can be cited in external content. Every claim carries `Source:` and `Last verified:` lines. If a claim is not in this file, do not assert it externally — see `SKILL.md` pre-return checklist § 7.

For the differentiator pillars these proofs anchor, see `differentiation.md`.

## 1. Accuracy claims

### 1.1 Up to 99% accuracy (headline real number)

> *Up to 99% accuracy* on documents that break general-purpose AI.

- **Use as:** the headline accuracy real-number on pitch decks, one-pagers, and landing-page hero.
- **Pair with:** the 96.2% Air France/KLM specific result (see § 1.2) as the defensible-against-skepticism number.
- **Do not use:** comparative framings like *"more accurate than X"* as the headline. Real numbers beat relative claims.
- **Source:** EyeLevel/GroundX 2026 sales deck.
- **Last verified:** 2026-05-14.

### 1.2 Air France / KLM — 96.2% accuracy

> Air France/KLM hit **96.2% accuracy** on visually complex policy documents, beating their **60% target**. The customer-service assistant clears human-level accuracy on questions that take new agents nine months of training to answer.

- **Industry:** travel.
- **Outcome:** customer-service assistant grounded in thousands of policy documents — fare tables, baggage rules, refund decision trees, annotated software screenshots.
- **Engagement length:** three-month engagement.
- **Quote available:** Karin Oskam, Knowledge Management Manager at Air France/KLM — *"The Valantor platform delivered truly impressive results, and the bot's ability to improve over such a short period was amazing."*
- **Source:** valantor.com Air France/KLM customer story.
- **Last verified:** 2026-05-14.

### 1.3 DocBench — superhuman performance

> Superhuman performance on the public DocBench document-comprehension benchmark.

- **Use as:** third-party benchmark validation in technical sections.
- **Source:** eyelevel.ai blog post — *"GroundX Achieves Superhuman Performance in Document Comprehension on DocBench."*
- **Last verified:** 2026-05-14.

### 1.4 Head-to-head testing wins

> In head-to-head testing, GroundX significantly outperforms many popular RAG tools, especially with complex documents at scale.

- **Use as:** competitive context in technical sections.
- **Source:** Three eyelevel.ai blog posts:
  - `eyelevel.ai/post/most-accurate-rag`
  - `eyelevel.ai/post/guide-to-document-parsing`
  - `eyelevel.ai/post/do-vector-databases-lose-accuracy-at-scale`
- **Last verified:** 2026-05-14.

## 2. Business outcomes

### 2.1 AskVet — margin doubling, autonomous resolution

> AskVet **doubled gross margin from 40% to 80%** by operationalizing a decade of veterinary data on GroundX. **VERA™, the world's first digital veterinarian, autonomously handles 70–85% of user questions.** Trained on 2 million+ chats, scanned medical records, diagnostic photos, and consult notes.

- **Industry:** animal health.
- **Outcome:** VERA™ digital veterinarian, operationalized as a turnkey enterprise platform spanning companion and farm animal verticals.
- **Quote available:** Cal Lai, Founder and CEO of AskVet — *"Valantor created foundational technology that allowed us to very quickly and rapidly scale up this virtual veterinarian. We couldn't have done it without the underlying technology that we built around Valantor's platform."*
- **Source:** valantor.com AskVet customer story.
- **Last verified:** 2026-05-14.

### 2.2 FraudX — insurance-fraud Outcome Plug-in (operational ROI)

> FraudX delivers **40× faster claim file review** and **10× more files reviewed per day** at directional reduction in loss ratio. *EyeLevel internal benchmark; "Actual results vary."* Three named customer voices on the record across carriers, claims operations, and defense counsel.

- **Industry:** insurance fraud investigation — production anchor in construction workers' compensation.
- **Outcome:** four-surface AI investigator (FraudX Score, Chat with Claims, Evidence Package, Network Analysis) that ingests the full claim file, runs 20+ investigator-defined fraud checks, and delivers a cited, source-linked dossier defensible from day one. See `product.md` § 6 for the capability detail.
- **Buyer voices:** Kirk Willis (CEO, Willis Law Group); Andriana Vamvakas (President, Andromeda Advantage); Dan Hickey (CEO, Tradesman/Roosevelt Road). Full quotes in § 5 quote bank.
- **Required qualifier:** the 40× and 10× claims must carry *EyeLevel internal benchmark* attribution and the *"Actual results vary"* qualifier in every external use. Do not strip the qualifier in collateral.
- **Source:** FraudX 2026 May sales deck.
- **Last verified:** 2026-05-17.

## 3. Logos and scale

### 3.1 Trusted-by logos

> Trusted by Air France, Dartmouth, Samsung, and 3,000+ global developers.

- **Source:** GroundX On-Prem Helm chart repo README; eyelevel.ai homepage.
- **Last verified:** 2026-05-14.

### 3.2 Platform scale

> 7B+ tokens ingested on the platform.

- **Use as:** scale signal in technical and investor-facing content.
- **Source:** eyelevel.ai messaging.
- **Last verified:** 2026-05-14.
- **Note:** the GroundX On-Prem Helm chart README cites 2B+ tokens; that figure may be out of date. Use 7B+ as the current external number.

### 3.3 Training corpus

> Vision model fine-tuned on **1 million+ pages** of enterprise documents.

- **Use as:** technical credibility anchor for the vision-model claim.
- **Source:** GroundX On-Prem Helm chart repo README.
- **Last verified:** 2026-05-14.

## 4. Partnerships and third-party validation

### 4.1 Red Hat — OpenShift AI quickstart

> Red Hat shipped an official OpenShift AI quickstart for GroundX: `rh-ai-quickstart/Billing-extraction-with-GroundX`. Tags: *Product: OpenShift AI / Partner: EyeLevel / Partner product: GroundX / Business challenge: Data extraction.*

- **Use as:** third-party validation of the on-prem deployment story. Especially powerful for regulated-industry buyers and OpenShift shops.
- **State note:** GroundX On-Prem itself is **GA**. The public Helm chart README (`github.com/eyelevelai/groundx-on-prem`) carries an "Open Beta" tag that is stale; treat the README as authoritative for capabilities and dependencies, not lifecycle state. See `../sources/README.md` § 1.
- **Source:** Red Hat AI quickstarts repo.
- **Last verified:** 2026-05-14.

### 4.2 Seamless Partners coverage

> Seamless Partners' independent analysis frames GroundX as a new operating layer for how enterprises run on visually complex documents.

- **Use as:** analyst-style third-party coverage.
- **Source:** Seamless Partners article summarized on valantor.com.
- **Last verified:** 2026-05-14.

## 5. Quote bank

Pull these directly when a customer voice is needed.

| Customer | Speaker / role | Quote |
| --- | --- | --- |
| Air France/KLM | Karin Oskam, Knowledge Management Manager | *"The Valantor platform delivered truly impressive results, and the bot's ability to improve over such a short period was amazing."* |
| AskVet | Cal Lai, Founder and CEO | *"Valantor created foundational technology that allowed us to very quickly and rapidly scale up this virtual veterinarian. We couldn't have done it without the underlying technology that we built around Valantor's platform."* |
| Willis Law Group (FraudX) | Kirk Willis, CEO | *"FraudX is an absolute game changer for how the industry fights insurance fraud."* |
| Andromeda Advantage (FraudX) | Andriana Vamvakas, President | *"With FraudX, we now have the AI power to uncover false claims and connect the dots."* |
| Tradesman / Roosevelt Road (FraudX) | Dan Hickey, CEO | *"With FraudX, we're combining AI with legal and investigative strength to protect our clients."* |

## 6. What this file does not cover

- Internal-only customer numbers or accuracy figures. If a claim is not externally publishable, it does not belong here.
- Master-brand altitude claims (Visual Intelligence category metrics, AI+humans accountability framing, Outcome Plug-in vertical economics). Those belong to `master-brand-gtm/references/proof-points.md` framed at master-brand altitude.
- Speculative metrics ("up to 10x faster", "save N FTEs"). If a real customer has supplied the number, request inclusion through the source-attribution process; do not extrapolate.
- Market-framing facts such as TAM, category growth, customer counts, competitor
  shares, or industry economics unless they have an external source or an
  owner-approved use record. Owner-approved facts need owner, date, qualifier,
  allowed surfaces, and re-verification cadence. Until then, treat them as
  source-pending and keep them out of external product guidance.

## 7. Verification cadence

Each proof point's `Last verified:` date is the last day a maintainer confirmed it remains accurate and approved-for-external. Re-verify quarterly or before a major external use (analyst briefing, investor pitch, public press piece). Stale claims should be removed rather than left in place.
