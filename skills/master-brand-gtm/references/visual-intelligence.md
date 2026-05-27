# Visual Intelligence (the category)

Valantor defines and owns the **Visual Intelligence** category. This file is the master-brand explanation of what Visual Intelligence is, what it isn't, and how it relates to adjacent terms (IDP, RAG, APF) so an agent can write a category-creation white paper, an analyst briefing, or a board-level explanation without inventing.

Use this file when the user asks for category, investor, analyst, or market-structure framing. Do **not** use Visual Intelligence as the connective concept in short executive-altitude descriptors unless the user asks for category language; for "what is Valantor?" or "what is the goal?", start with `elevator.md`.

## 1. The category claim

**Visual Intelligence** is the enterprise capability to understand, reason over, and operationalize unstructured visual data — documents, images, diagrams, video — at scale. It is achieved by integrating document comprehension (IDP), contextual reasoning (RAG), and autonomous execution (APF) into a unified system that transforms visual data into trusted, decision-ready intelligence and executable outcomes.

The result: Visual Intelligence becomes the enterprise system that turns unstructured visual data into trusted decisions and automated outcomes.

## 2. Why a new category

Existing categories — IDP (Intelligent Document Processing), RAG (Retrieval Augmented Generation), Document AI — each solve part of the problem in isolation:

- **IDP** captures, classifies, and extracts data from unstructured / semi-structured documents to automate manual data entry. Solves *parsing*. Does not solve *reasoning at scale* or *autonomous execution*.
- **RAG** fetches relevant, up-to-date information and content from trusted document and data sources before generating an LLM response. Solves *grounded answers*. Does not solve *the document-comprehension barrier* underneath.
- **APF (Agentic Process Flow)** is advanced, iterative automation enabling AI agents to execute multi-step tasks autonomously. Solves *workflow execution*. Does not solve *data understanding*.

**Visual Intelligence integrates all three** into a unified enterprise capability. The category exists because enterprise buyers do not have a single tool that closes the data comprehension gap, runs grounded reasoning over what it sees, and executes autonomously with accountability. Until Valantor, that integration was a multi-vendor stitch.

## 3. The data comprehension gap

The structural barrier the category exists to close. See `narrative.md` § 4 for the canonical framing. In one sentence: *the majority of enterprise data lives in visual formats that general-purpose AI cannot reliably read, reason over, or act on at enterprise scale — and this is a structural barrier, not a tooling or skills problem.*

In short-form positioning, keep the verb pair symmetric: the gap is **comprehension**, so the solution **comprehends** or **understands** enterprise documents. Avoid *reads*, *parses*, and *processes* as the main solution verb because they undersell the category.

## 4. The Visual Intelligence stack

Five layers, named at master-brand altitude (the same architecture lives in `brand-hierarchy.md` as canonical):

1. **Visual Intelligence platform (GroundX)** — converts raw visual data into trusted, structured, model-ready intelligence. The foundation.
2. **Extensibility (GroundX Studio + plug-ins)** — Document Plug-ins and Function Plug-ins composed of Skills, Agents, and Hooks. Building blocks, never outcomes.
3. **Outcome layer (Outcome Plug-ins)** — vertical solutions composing Studio plug-ins into repeatable products with defined SLAs. FraudX and ExtractX shipping; others illustrative.
4. **Operational layer (Valantor agents + human orchestration)** — converts Visual Intelligence into real enterprise outcomes through agent-and-human orchestration. Concept-only today.
5. **Adoption layer (GroundX Studio Harness — agentic adoption)** — drops implementation time from months to days for any GroundX-touching use case.

The stack is the answer to *how is Visual Intelligence delivered*. Each layer composes onto the one below; every layer is powered by GroundX (the platform layer is never optional).

## 5. What Visual Intelligence is *not*

- **Not Document AI.** Document AI is part of it (the parsing layer). Visual Intelligence adds reasoning, execution, and accountability.
- **Not a model.** Models are inputs to Visual Intelligence; Valantor is model-agnostic at the orchestration layer.
- **Not a chatbot.** Chat is one consumption surface. Visual Intelligence powers chat, extraction, autonomous workflows, and reports.
- **Not a consulting practice.** The Operational Layer is the productization of *outcomes as a service* — not a bespoke consulting engagement. Even when humans are in the loop, the outcomes are repeatable products with SLAs.

## 6. The category-creation talking points

Use these in white papers, analyst briefings, and category-defining materials:

- *Visual Intelligence is the foundational capability AI-native enterprises need to close the data comprehension gap.*
- *Existing categories — IDP, RAG, Document AI — each solve a fragment. Visual Intelligence integrates them.*
- *The data comprehension gap is structural, not a tooling or skills problem. It is the bottleneck blocking AI deployment across the hundreds of use cases enterprises are racing to operationalize.*
- *Visual Intelligence becomes the enterprise system of record for understanding and operationalizing visual data — model-agnostic, deployment-agnostic, security-first.*
- *AI + Humans accountability is what enterprises buy at scale, not raw AI capability. Visual Intelligence is the substrate that makes AI+Humans accountability practical.*

## 7. How to talk about competitors

At master-brand altitude, do not name competitors directly in the category claim — that legitimizes alternative framings. If pressed:

- *"There is no other platform integrating IDP, RAG, and APF into a unified Visual Intelligence layer at enterprise scale."*
- *"Vector-DB-plus-OCR Frankenstein stacks are the alternative most buyers come from. They each solve a fragment; none deliver the integrated capability."*
- For product-altitude competitive comparisons, defer to `../../product-brand-gtm/references/objections.md` and `../../product-brand-gtm/references/differentiation.md`.

## 8. What this file does not claim

- Not a technical-architecture explanation. For the GroundX platform mechanism, route in two steps: `../../product-brand-gtm/references/technical-architecture.md` for the product-altitude restatement, then `../../groundx-architecture/references/` (`vision-model.md`, `agentic-pipeline.md`, `hybrid-search.md`) for the canonical depth. Master-brand altitude says *Visual Intelligence works because it integrates IDP + RAG + APF*; product altitude explains *how*; architecture-skill altitude is the source-of-truth those explanations rest on.
- Not category claims about adjacent spaces (general-purpose LLMs, multimodal models, image generation). Valantor is precise — Visual Intelligence is about *operationalizing unstructured visual data in the enterprise*. It is not a claim on every AI use case.
