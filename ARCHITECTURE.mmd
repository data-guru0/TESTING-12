flowchart TD

    User(["👤 User\nBrowser / API Client"])

    subgraph AWS["☁️ AWS Cloud — us-east-1"]

        ALB["🔀 ALB — Application Load Balancer\n:80 → App    :8001 → Red Team"]

        subgraph ECS["🖥️ ECS Fargate — Auto-scaling Containers"]
            direction LR

            subgraph AppTask["App Task"]
                API["⚡ FastAPI :8000\nREST API + Background Worker"]
                TZ["🔀 TensorZero :3000\nLLM Gateway Sidecar"]
            end

            subgraph RedTask["Red Team Task"]
                PyRIT["🔴 PyRIT 0.14.0\nJailbreak · XPIA\nCrescendo · Skeleton Key"]
            end
        end

        subgraph SecLayer["🔒 Security — every request passes through"]
            direction LR
            Auth["🔑 API Key\nX-API-Key header\n→ 401 if wrong"]
            RateL["⏱️ Rate Limiter\n10 req / 60s per IP\nvia Redis counter"]
            GIn["🛡️ Bedrock Guardrail\nInput Check\nHate · PII · Weapons\nPrompt Attacks"]
        end

        Queue["📨 Redis Stream\nJob Queue — async processing"]

        subgraph SmartLookup["⚡ Smart Lookup — saves LLM cost"]
            direction LR
            SC["Redis\nSemantic Cache\ncosine sim ≥ 0.85\nInstant return"]
            LTM1["pgvector\nExact LTM Match\nsim ≥ 0.88\nReturn stored report"]
            LTM2["pgvector\nRelated LTM\n0.5–0.88 sim\nContext → Writer Agent"]
        end

        subgraph Pipeline["🤖 LangGraph — Multi-Agent Pipeline"]
            direction LR
            A1["① Search Agent\nFinds key facts\nUses session history"]
            A2["② Summarize Agent\nCondenses findings\ninto bullet points"]
            A3["③ Writer Agent\nFull structured report\nUses LTM context"]
            A4["④ Critic Agent\nFact-checks report\nRetries if fails"]
        end

        GOut["🛡️ Bedrock Guardrail\nOutput Check\nBlocks harmful responses"]

        subgraph SaveEval["💾 Save + Evaluate"]
            direction LR
            Save["Store Results\nRedis — cache + session\nPostgreSQL — LTM vector"]
            Eval["📊 LLM-as-Judge\nRelevance · Completeness\nHallucination · Quality"]
        end

        subgraph DataLayer["🗄️ Storage Layer"]
            direction LR
            Redis["⚡ Redis ElastiCache\nSemantic cache\nSession memory\nJob queue"]
            RDS["🗄️ RDS PostgreSQL 15\n+ pgvector extension\n384-dim embeddings\nLong-term memory"]
        end

        Secrets["🔐 Secrets Manager\nAll API keys + config\nLoaded at startup"]
        ECR["📦 ECR\n3 Docker images\napp · pyrit · tensorzero"]
        CW["📋 CloudWatch\nContainer logs · 7 days"]
        EB["⏰ EventBridge\nWeekly red team trigger\nEvery Monday 2am UTC"]

    end

    subgraph LLMs["🧠 LLM Providers"]
        direction LR
        GPT["🟢 OpenAI GPT-4o\nPrimary"]
        Groq["🟡 Groq\nllama-3.1-8b-instant\nFallback"]
    end

    ST["🔢 SentenceTransformer\nall-MiniLM-L6-v2\n384-dim — runs in-process"]
    LS["📊 LangSmith\nTraces every agent node\n4 eval scores per report"]

    subgraph CICD["🔄 CI/CD + Infrastructure as Code"]
        direction LR
        GH["⚙️ GitHub Actions\nOn every git push:\nBuild 3 Docker images\nPush to ECR → Deploy to ECS\nAuto rollback on failure"]
        TF["🏗️ Terraform\nProvisions all AWS:\nVPC · Subnets · ECS · ALB\nRDS · ElastiCache · ECR\nBedrock · Secrets Manager\nIAM · EventBridge · S3 lock"]
    end

    %% ── Entry flow ────────────────────────────────────────────
    User -->|"HTTPS request"| ALB
    ALB -->|"app traffic"| Auth
    Auth --> RateL --> GIn
    GIn -->|"safe ✓"| Queue

    %% ── Smart lookup ──────────────────────────────────────────
    Queue --> SC
    SC -->|"cache miss"| LTM1
    LTM1 -->|"ltm miss"| LTM2
    SC -->|"cache hit → skip agents"| GOut
    LTM1 -->|"ltm hit → skip agents"| GOut

    %% ── Agent pipeline ────────────────────────────────────────
    LTM2 --> A1 --> A2 --> A3 --> A4
    A4 -->|"❌ fail → retry"| A1
    A4 -->|"✅ pass"| GOut

    %% ── Output + save ─────────────────────────────────────────
    GOut --> Save
    GOut --> Eval
    Save --> User

    %% ── LLM routing ───────────────────────────────────────────
    A1 & A2 & A3 & A4 & Eval -->|"POST /inference"| TZ
    TZ -->|"primary"| GPT
    TZ -->|"fallback"| Groq

    %% ── Embeddings ────────────────────────────────────────────
    SC & LTM1 & LTM2 & Save -->|"embed text"| ST

    %% ── Storage ───────────────────────────────────────────────
    SC & Save <-->|"read / write"| Redis
    LTM1 & LTM2 & Save <-->|"vector search / store"| RDS

    %% ── Safety ────────────────────────────────────────────────
    GIn & GOut -->|"guardrail check"| Bedrock_svc["AWS Bedrock\nGuardrails"]

    %% ── Observability ─────────────────────────────────────────
    A1 & A2 & A3 & A4 & Eval -->|"@traceable"| LS

    %% ── Red Team ──────────────────────────────────────────────
    ALB -->|"port 8001"| PyRIT
    PyRIT -->|"attack requests"| ALB
    EB -->|"weekly schedule"| PyRIT

    %% ── Infra ─────────────────────────────────────────────────
    API -->|"reads on startup"| Secrets
    GH -->|"push images"| ECR
    ECR -->|"pull on deploy"| ECS
    ECS -->|"logs"| CW
    TF -.->|"creates all resources"| AWS
