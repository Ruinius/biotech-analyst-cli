## 2024-06-17 - O(N*M) nested loop set comprehension bottleneck
**Learning:** Found a quadratic time complexity bottleneck in `src/utils/landscape/reconciliation.py` where a nested `any()` loop recalculated normalized strings (`normalize_drug_name()`) and set comprehensions for every candidate name against every existing group.
**Action:** When comparing sets or groups of string data against multiple items in Python, precompute lowercase/normalized transformations outside of loops and use `set.isdisjoint()` for O(1) intersection checks rather than `any()` loops.
