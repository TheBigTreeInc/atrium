# Atrium 0.5.84 — Market Grove shared exchange source candidate

Base: Library Atrium 0.5.83 source ZIP, not confirmed checkout of current Git main. Version is 0.5.84. Source-owned game work is in `games/market-grove/`, `tools/build_market_grove_spec.py`, `tools/market_grove_reference_import.py` and `docs/ATRIUM_MARKET_GROVE_EXCHANGE_084.adoc`. Tests are `tests/test_market_grove_exchange_084.py`, `tests/test_market_grove_reference_import_084.py` and existing Market Grove suites.

Market Grove is already an Atrium child: do **not** register it as a new ZipRunner project or create an alternate launcher. Market state is globally shared and durable. No extra TaviX build is necessary; current immutable Atrium 1.0.4 remains unchanged.

Security: Gold in this source is game practice credits only. There is no Wallet trade transfer, no public-rate fetch in trusted LoopRD jobs, no automatic grant of `market:reference`, and no usable production Tavi Wallet until Social owner implements, reviews and approves the separate service escrow and settlement contract. No fiat, redemption or creator payouts.

Operator actions: import source ZIP in the existing Atrium workspace, preserve `.git`, `.env`, DBs and local approved configuration, backup child SQLite state, run Windows ZipRunner and LoopRD isolated-child acceptance, verify operator-private rate imports and two-account shared fills. Do not release or publish without separate operator approval.
