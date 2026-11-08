workspace "Atrium" "C4 model of the Atrium game marketplace, LoopRD runtime component, source-only multiplayer adapters, and Tavi extension." {
    model {
        player = person "Player" "Browses approved games in Atrium or opens its extension inside Tavi."
        operator = person "Atrium operator" "Reviews publisher and deployment trust, configures catalog gateways, and controls releases."

        tavi = softwareSystem "Tavi Messenger" "External messenger and extension host; owns its navigation and client lifecycle." "External"
        social = softwareSystem "Tavi Social" "External Social account, session, contact, and challenge authority. Runtime verification is not yet connected to Atrium Checkers." "External"
        looprd = softwareSystem "LoopRD / DAPI" "External specification runtime that executes the Atrium component and manages its authenticated API and database." "External"
        otherGames = softwareSystem "Independent games" "Game-owned LoopRD services and hosted game frontends (for example Life); their sessions and rules are not implemented inside Atrium." "External"

        atrium = softwareSystem "Atrium" "Reviewed game catalog, registration, game discovery, generic lobbies, and source-level Checkers multiplayer integration." {
            portal = container "Atrium browser portal" "Static storefront and game discovery, independent of the Tavi messenger." "HTML, CSS, JavaScript" {
                portalShell = component "Portal and navigation" "Renders storefront and validates source availability; embedded Tavi uses compact independent catalog/installed-game statuses, without duplicate host navigation or misreporting disabled offline sources as outages." "web/main.mjs, HTML, CSS"
                reviewedCatalogClient = component "Reviewed release client" "Loads and verifies published immutable app snapshots and configured catalog origin." "JavaScript"
                hostedGameClient = component "Hosted game catalog client" "Loads and validates public trusted LoopRD hosted game projections without credentials." "JavaScript"
                iframeHost = component "Sandboxed app host" "Checks reviewed HTML SHA-256 and embeds it in a restricted iframe." "JavaScript"
                checkersPlayer = component "Remote Checkers player" "Consumes host-authenticated match state and server-provided legal actions; does not execute rules." "JavaScript" {
                    tags "SourceOnly"
                }
            }
            tavix = container "Atrium TaviX extension" "Embedded Atrium catalog and navigation using the host SDK; reviewed 1.0.4 remains immutable and new styling is future release source." "JavaScript, TaviX SDK" {
                taviBridge = component "TaviX launch adapter" "Requests reviewed game surfaces and navigation from the Tavi host, without becoming a game server." "JavaScript"
                installedGameBridge = component "Installed TaviX game consumer" "Negotiates tavix.installed-games/v1, validates read-only game descriptors and requests version-pinned host launch; Tavi enforces authorization." "JavaScript"
                taviSdk = component "TaviX host protocol adapter" "Validates host responses and communicates through the Tavi extension protocol." "JavaScript"
            }
            api = container "Atrium LoopRD component" "One LoopRD component, composed from registry, arcade, Checkers, and discovery fragments; activated through external DAPI." "LoopRD YAML and Python handlers" {
                registry = component "Publisher and release registry" "Submits, reviews, disables, and lists publisher releases; controls immutable reviewed apps." "Python and SQLAlchemy"
                discovery = component "Trusted deployment discovery" "Accepts service-bound, monotonic discovery observations and manages trusted source bindings and candidate lifecycle." "Python and SQLAlchemy"
                sidecar = component "Portable game contract validator" "Validates atriumd/v1 metadata independently of deployment URLs." "Python"
                registrationIngress = component "Registration notice ingress" "Accepts operator-bounded LoopRD registration notices without automatic public publication." "Python and SQLAlchemy"
                hostedProjection = component "Hosted catalog projection" "Projects active trusted deployment and game metadata into bounded, safe public game entries." "Python and SQLAlchemy"
                arcade = component "Arcade lounge and table contracts" "Declares shared lounges, tables, match records, and Staff eligibility metadata in the included arcade model." "LoopRD YAML"
                checkersOracle = component "Checkers stateless rules oracle" "Implements the included Checkers game rules adapter and stateless evaluate endpoint." "Python in generated LoopRD handler"
                lobbyCore = component "Hostless lobby source" "Persists private lobbies and retries via trusted callbacks; not wired as a public authenticated production route." "Python" {
                    tags "SourceOnly"
                }
                socialAdmission = component "Social challenge admission adapter" "Checks original accepted Social challenge and verified contact/session callbacks supplied by a trusted host." "Python" {
                    tags "SourceOnly"
                }
                checkersRoutes = component "Trusted Checkers route dispatcher" "Strictly dispatches create, join, inspect, legal-actions, and move operations; not registered as public LoopRD handlers." "Python" {
                    tags "SourceOnly"
                }
                checkersHost = component "Checkers trusted host" "Requires verified Social actor and approved lobby before authorizing match operations." "Python" {
                    tags "SourceOnly"
                }
                checkersAuthority = component "Checkers match authority" "Owns revisions, seats, idempotency, move persistence, and turn transitions using the game rules engine." "Python and SQLite" {
                    tags "SourceOnly"
                }
            }
            registryStore = container "Atrium registry database" "DAPI-owned publisher, releases, discovery candidate, and trusted instance tables (schema v6)." "SQLite" {
                tags "Database"
            }
            checkersStore = container "Checkers match store (source/tests)" "Local transactional match and request ledger used by the source-only Checkers authority, not a production deployed data store." "SQLite" {
                tags "Database,SourceOnly"
            }
            lobbyStore = container "Hostless lobby store (source/tests)" "Local private lobby and outbox state for source-level trusted multiplayer adapters." "SQLite" {
                tags "Database,SourceOnly"
            }
            catalogGateway = container "Optional catalog gateway" "Operator-started loopback HTTP server exporting fresh reviewed and hosted catalog snapshots; public TLS proxy requires separate deployment." "Python HTTPServer"
            registrationReader = container "Deployment registration reader" "Operator-run CLI that reads LoopRD component inventory and sibling atriumd.yaml documents and submits trusted observations." "Python CLI"
            offlineCandidateTools = container "Offline game candidate tools" "Operator-run source-only pack/verify of external offline web games and developer TaviX preview generation; no installation, publication or game execution." "Python CLI" {
                offlineBundleValidator = component "Offline game candidate validator" "Verifies exact external file digests, bounded archive paths, offline references and manifest contract." "Python"
                offlineBundlePackager = component "Offline game candidate packager" "Builds a deterministic ZIP and metadata from independent game assets." "Python"
                offlineTavixPreview = component "Offline TaviX preview converter" "Transforms only verified candidate bytes into a bounded developer-only TaviX app/lockfile; does not install, sign or publish." "Python"
            }
            marketGrove = container "Market Grove LoopRD subcomponent" "Bundled independent LoopRD child game with its own market operations, scheduled clearing job, and game-owned state." "LoopRD YAML and Python"
            marketStore = container "Market Grove game database" "Game-owned market order, state, and trade history storage." "SQLite" {
                tags "Database"
            }
        }

        player -> portal "Browses the game library and launches reviewed web entries" "Browser / HTTPS"
        player -> tavix "Opens Atrium through Tavi's embedded extension" "Tavi UI"
        operator -> offlineCandidateTools "Packages and verifies independent game candidate builds (not installs)" "Local CLI"
        offlineBundlePackager -> offlineBundleValidator "Verifies generated candidate before returning digest" "Python"
        offlineTavixPreview -> offlineBundleValidator "Validates candidate before preview conversion" "Python"
        operator -> registrationReader "Runs registration synchronization with private operator configuration" "CLI"
        operator -> api "Reviews publisher releases and trusted deployments" "Scoped LoopRD API"
        tavi -> tavix "Hosts the extension and owns global navigation" "TaviX host protocol"
        tavix -> tavi "Requests navigation and reviewed game launch" "TaviX messages"
        portal -> otherGames "Opens approved hosted game URL, if configured and available" "HTTPS"
        tavix -> otherGames "Requests approved game surfaces through host; not a gameplay authority" "TaviX / hosted web"
        api -> looprd "Is executed by the installed DAPI runtime" "LoopRD/v1"
        api -> registryStore "Reads and writes registry and trust records" "SQLAlchemy / SQLite"
        api -> checkersStore "Source-only match state and idempotency persistence" "SQLite"
        api -> lobbyStore "Source-only lobby and outbox persistence" "SQLite"
        marketGrove -> looprd "Runs as an independent child component when activated" "LoopRD/v1"
        marketGrove -> marketStore "Reads and writes its game-owned market state" "SQLite"
        registrationReader -> looprd "Reads configured component inventory and portable registration sidecars" "LoopRD API, authenticated HTTP"
        registrationReader -> api "Delivers independently validated discovery observations" "LoopRD API, service scope"
        catalogGateway -> registryStore "Reads current reviewed or active hosted catalog rows" "SQLite read-only"
        portal -> catalogGateway "Optional configured catalog source; not connected in shipped offline snapshot" "GET JSON, HTTP behind operator TLS proxy"
        portal -> api "Optional hosted catalog endpoint; requires runtime configuration" "GET JSON, LoopRD API"
        portal -> hostedProjection "Reads hosted games via the configured LoopRD endpoint (deployment gated)" "GET JSON"
        tavix -> api "Optional configured hosted catalog endpoint; not bound in immutable 1.0.4" "GET JSON"
        api -> social "Source-only verified-session, original-challenge, and contact callback contract; no live binding" "Typed host callbacks"

        portalShell -> reviewedCatalogClient "Requests reviewed releases"
        portalShell -> hostedGameClient "Requests active hosted games"
        portalShell -> iframeHost "Loads selected reviewed HTML in sandbox"
        reviewedCatalogClient -> catalogGateway "Fetches published immutable app snapshot when configured" "GET /catalog.json"
        hostedGameClient -> catalogGateway "Fetches approved hosted game projection when configured" "GET /hosted-games.json"
        hostedGameClient -> hostedProjection "Consumes LoopRD-generated hosted catalog JSON when configured" "GET /catalog/hosted-games"
        checkersPlayer -> checkersRoutes "Source-only match protocol; requires authenticated same-origin host" "HTTP JSON"
        taviBridge -> taviSdk "Uses typed host SDK"
        installedGameBridge -> taviSdk "Requests authorized installed game inventory and launch"
        taviBridge -> hostedGameClient "Reads hosted catalog from configured trusted source"
        registry -> registryStore "Stores publication and publisher records" "SQLAlchemy"
        arcade -> registryStore "Declares lounge and table models in the shared Atrium database" "LoopRD models"
        discovery -> registryStore "Stores deployment bindings, observations, receipts and candidates" "SQLAlchemy"
        discovery -> sidecar "Validates portable sidecar identity and metadata"
        registrationIngress -> registryStore "Persists registration notice metadata" "SQLAlchemy"
        hostedProjection -> registryStore "Projects only active trusted instances and deployment launch bindings" "SQLAlchemy"
        checkersRoutes -> checkersHost "Delegates authorized match operations"
        socialAdmission -> checkersHost "Supplies verified account and approved original challenge"
        checkersHost -> checkersAuthority "Calls privilege-checked match operations"
        checkersAuthority -> checkersOracle "Uses the canonical game rules engine" "Python"
        checkersAuthority -> checkersStore "Commits moves and idempotency records" "SQLite"
        lobbyCore -> lobbyStore "Stores private lobby/outbox records" "SQLite"
        socialAdmission -> social "Would query original Social challenge and current session/contact through injected callbacks; not live" "Host callbacks"
    }

    views {
        component offlineCandidateTools atrium_offline_candidate_components "Independent offline-game packaging, integrity verification and developer preview conversion (no install path)" {
            include *
            autoLayout lr
        }

        systemContext atrium atrium_context "Atrium's product boundary and external owners" {
            include *
            autoLayout lr
        }
        container atrium atrium_containers "Atrium applications and stores, including explicitly source-only services" {
            include *
            autoLayout lr
        }
        component api atrium_runtime_components "LoopRD API responsibilities: publisher, discovery, catalog, and source-only game authority" {
            include *
            autoLayout lr
        }
        component portal atrium_portal_components "Browser portal discovery, sandbox and remote-game UI" {
            include *
            autoLayout lr
        }
        component tavix atrium_tavix_components "TaviX hosted extension and host protocol bridge" {
            include *
            autoLayout lr
        }
        dynamic api atrium_discovery_flow "When configured: discover and register game sidecar, then project active hosted catalog" {
            registrationReader -> discovery "Submit service-bound observation"
            discovery -> sidecar "Validate deployment-independent sidecar"
            discovery -> registryStore "Store trusted candidate and deployment record"
            hostedProjection -> registryStore "Read only active trusted deployment/game bindings"
            portal -> hostedProjection "Request hosted catalog through configured LoopRD endpoint"
            autoLayout lr
        }
        dynamic api atrium_checkers_source_flow "Source-only: an accepted Social challenge to authoritative Checkers move; not a public route" {
            socialAdmission -> checkersHost "Provide verified account and original challenge approval"
            checkersRoutes -> checkersHost "Dispatch trusted create or move call"
            checkersHost -> checkersAuthority "Authorize the subject and operate its match"
            checkersAuthority -> checkersOracle "Validate legal move and compute next state"
            checkersAuthority -> checkersStore "Commit revision and idempotency response"
            autoLayout lr
        }
        styles {
            element "Person" {
                shape Person
                background #225a44
                color #ffffff
            }
            element "Software System" {
                background #255c4d
                color #ffffff
            }
            element "Container" {
                background #417967
                color #ffffff
            }
            element "Component" {
                background #d5eadb
                color #193d2e
            }
            element "Database" {
                shape Cylinder
            }
            element "SourceOnly" {
                background #f4ead1
                color #4d4130
            }
            element "External" {
                background #667580
                color #ffffff
            }
        }
    }
}
