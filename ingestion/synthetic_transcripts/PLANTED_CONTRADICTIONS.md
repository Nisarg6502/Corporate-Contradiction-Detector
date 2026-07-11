# Planted contradictions (ground truth)

These are deliberately seeded into the **synthetic** earnings-call transcripts so
Checkpoint 5 (contradiction detection) has a known target. Each contradicts a
claim in NVIDIA's **real** FY2026 10-K (`0001045810-26-000021`). The transcript
speaker asserts the opposite of what the filing discloses.

| ID  | Topic | Transcript claim (synthetic) | Real filing claim (10-K) | Expected severity |
| --- | ----- | ---------------------------- | ------------------------ | ----------------- |
| PC1 | Gross margin / profitability | Kress (Q1): gross margin *expanded* to a record, *no meaningful inventory charges*. | MD&A: "Gross margin **decreased** in fiscal year 2026... **$4.5 billion charge** associated with H20 excess inventory." | **high** |
| PC2 | Geographic / customer concentration | Huang (Q3): revenue *broadly spread across thousands of customers*, *no meaningful concentration*. | Risk factors: "A significant amount of our revenue stems from a **limited number of partners and distributors**... **concentration of sales**." | **high** |
| PC3 | Regulatory / legal risk | Huang (Q2): export controls have had *no material impact*, *China fully accessible*, no future licensing risk. | Risk factors: U.S. export restrictions/licensing requirements **materially impact** China sales; a $4.5B H20 charge already resulted. | **high** |

Benign turns (aligned with filings) are also included in each transcript to test
for **false positives** — e.g. Huang saying competition is intensifying (Q3) and
demand outpaces supply (Q1) both match the filings and must NOT be flagged.
