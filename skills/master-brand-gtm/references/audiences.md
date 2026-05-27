# Audiences (master-brand altitude)

Persona-axis overlay on the master-brand message-axis. Use this file to adapt the master-brand pitch — defined in `buyer.md`, `narrative.md`, `investor-narrative.md`, and `ai-and-humans.md` — to a specific buyer persona at master-brand altitude.

For the existential-crisis dynamic that frames every persona, see `buyer.md` § 1. For the LOB-as-outcome-buyer routing, see `buyer.md` § 6. For product-altitude personas (CIO / VP Eng / Data Lead / LOB at the GroundX product level), see `../../product-brand-gtm/references/audiences.md` — that file owns product-altitude audience cuts.

**Master-brand audiences are typically more senior, more strategy-oriented, and more business-outcome-driven than product-altitude audiences.** The pitch shape shifts accordingly.

## 1. CEO

**What they care about.** Enterprise transformation, strategic positioning, competitive durability, board-level accountability for AI strategy.

**Pitch shape.**
- Lead with the category claim and the compounding strategic frame (`narrative.md`, `investor-narrative.md` § 3 control-plane positioning).
- Pillar order at master-brand altitude: category ownership → AI+humans accountability → infrastructure-grade compounding → regulated-vertical depth.
- Use the *infrastructure layer that lets AI-native enterprises close the data comprehension gap* one-line (from `investor-narrative.md` § 1).
- Emphasize: long-term partnership, multi-year contract, durable competitive positioning.
- De-emphasize: technical mechanism (defer to CIO and below).

## 2. CFO

**What they care about.** Multiples, predictability of revenue, infrastructure-grade economics, switching costs and durability of contracts, ROI of AI spend.

**Pitch shape.**
- Lead with the outcomes-vs-tools posture and the AI+humans-accountability valuation framing.
- Pillar order: infrastructure-grade economics → outcome-buying clarity → multi-year contract economics → category-defining positioning.
- Reference `ai-and-humans.md` § 3 (valuation signals) and `investor-narrative.md` § 6 (four valuation pillars).
- Emphasize: the Operational Layer's strategic posture (paying for outcomes, not tools) — explicitly flagged as concept-only today.
- Cite AskVet's 40% → 80% margin shift as the customer-economics proof at this altitude.
- De-emphasize: visual mechanism, product-feature lists.

## 3. Board / Director

**What they care about.** Governance, AI risk and accountability, strategic competitive positioning, capital allocation, M&A optionality.

**Pitch shape.**
- Lead with the assured-intelligence-not-best-effort framing and the AI + humans accountability story.
- Pillar order: governance → accountability → category positioning → vertical-thesis depth.
- Reference `ai-and-humans.md` (the strategic posture) and `verticals.md` (the where-we-deploy-first thesis).
- Emphasize: trust, governance, audit-trail, source-attribution, regulated-industry track record.
- De-emphasize: tactical sales motion, product-mechanism detail.

## 4. Investor (founder / executive briefing, fundraising)

**What they care about.** Category, defensibility, valuation profile, premium-multiple positioning, TAM and expansion.

**Pitch shape.**
- This is the primary audience for `investor-narrative.md` — read it as the authoritative file.
- Pillar order: category ownership → control-plane positioning → compounding logic → AI+humans valuation lever → regulated-vertical depth → defensibility moats.
- Lead with the one-sentence translation from `investor-narrative.md` § 1.
- Emphasize: category-defining, infrastructure-tier, multi-year durability, compounding defensibility.
- De-emphasize: tactical sales process, day-to-day product roadmap.

## 5. Analyst (industry analyst, market researcher, press)

**What they care about.** Category definition, market sizing, competitive landscape, vertical proof, differentiation, third-party validation.

**Pitch shape.**
- Lead with the category claim (`visual-intelligence.md` § 1) and the data comprehension gap framing.
- Pillar order: category definition → vertical proof (FraudX, ExtractX shipping) → third-party validation (Red Hat partnership) → strategic frame (AI+humans, Operational Layer concept).
- Reference Seamless Partners coverage (`proof-points.md` § 4.2) as the analyst-style independent-analysis precedent.
- Emphasize: precise category definition, named vertical proofs, named partnerships.
- De-emphasize: product-feature detail, internal-state details.

## 6. Industry leader / vertical executive (insurance, financial services, healthcare, public sector, energy)

**What they care about.** Vertical-specific outcomes, regulatory and compliance fit, peer proofs in the same vertical, deployment posture (on-prem, air-gapped), risk reduction.

**Pitch shape.**
- Lead with the vertical thesis and the Outcome Plug-in productization pattern.
- Pillar order: vertical-specific Outcome Plug-in (if shipping) or vertical-thesis fit (if not) → regulated-deployment capability → AI+humans accountability → infrastructure-grade contract economics.
- Reference `verticals.md` for the thesis and `outcome-playbooks.md` for the relevant Outcome Plug-in.
- Emphasize: on-prem / air-gapped deployment, Red Hat OpenShift quickstart, regulated-vertical accuracy bar (Air France / KLM 96.2% as the cross-vertical proof).
- De-emphasize: master-brand framing if the executive is asking *what does it do for my industry today.* Pivot to vertical-specific Outcome Plug-in (FraudX for insurance, ExtractX for document-ops) when available.

## 7. CIO / CTO / Head of AI (when at master-brand altitude)

**Audience context.** Technical executives appearing in master-brand conversations (an investor roadshow stop, a board presentation, a category-creation white paper review). Often facing the existential-crisis dynamic personally (see `buyer.md` § 1 and `../../product-brand-gtm/references/audiences.md` § 2–4).

**Pitch shape.**
- Lead with the implementation-scale pain and the platform-plus-Harness operational answer.
- Pillar order: data-comprehension-gap framing → platform-and-Harness operational answer → AI+humans accountability → governance / on-prem.
- Reference `../../product-brand-gtm/references/audiences.md` for the technical-buyer routing-around-hostility framing.
- Emphasize: the Harness as a force-multiplier (not a replacement) for the internal technical team; governance and on-prem reduce vendor risk.
- De-emphasize: outcomes-vs-tools framing as a primary lead (it reads as threatening to this audience — see `../../product-brand-gtm/references/audiences.md` § 3).

## 8. Persona cross-pitch rules

- **Do not pitch every pillar to every audience.** Three or four pillars in a master-brand conversation is plenty; saving one for follow-up creates a reason to meet again.
- **Match altitude first.** A CFO does not want the CIO pitch; an analyst does not want the investor pitch; an industry leader does not want the category-creation white-paper pitch verbatim.
- **Do not collapse personas into "the master-brand buyer."** A CEO and an analyst are both master-brand-altitude audiences, but they want different things. Use this file to keep the persona axis explicit.

## 9. When the persona is not yet known

Default to the **broader-universe master-brand pitch** from `buyer.md` § 4 — lead with the category claim, the data-comprehension-gap framing, and the assured-intelligence positioning. Ask discovery questions early (*"what role are you in?"*, *"are you focused on the strategic frame or the operational outcomes?"*, *"is this for investor materials or customer-facing?"*) to identify the persona, then shift accordingly.
