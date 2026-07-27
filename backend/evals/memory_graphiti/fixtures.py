"""Synthetic dialogue fixtures for the Graphiti spike.

2 tenants × 2 users × ~10 dialogues each — tests isolation and
retrieval quality across boundaries.
"""

TENANTS = [
    {"tenant_id": "tenant-alpha", "name": "Alpha Corp"},
    {"tenant_id": "tenant-beta", "name": "Beta Inc"},
]

USERS = [
    {"user_id": "user-alice", "name": "Alice"},
    {"user_id": "user-bob", "name": "Bob"},
]

# Dialogues per (tenant, user) — each is a list of (role, content) turns
# that should be ingested as episodes.
DIALOGUES: dict[tuple[str, str], list[list[tuple[str, str]]]] = {
    ("tenant-alpha", "user-alice"): [
        [
            ("user", "My preferred programming language is Python."),
            ("assistant", "Got it, you prefer Python. I'll keep that in mind."),
        ],
        [
            ("user", "Our team uses PostgreSQL for all databases."),
            ("assistant", "Noted — PostgreSQL is your default database."),
        ],
        [
            ("user", "Deploy to production every Friday at 5pm."),
            ("assistant", "Production deployments happen Friday 5pm."),
        ],
        [
            ("user", "I'm working on a project called Nebula."),
            ("assistant", "I'll remember you're working on project Nebula."),
        ],
        [
            ("user", "Use FastAPI for all new backend services."),
            ("assistant", "FastAPI is the standard for new backend services."),
        ],
        [
            ("user", "Our CI/CD pipeline uses GitHub Actions."),
            ("assistant", "CI/CD runs on GitHub Actions."),
        ],
        [
            ("user", "I prefer dark mode in all IDEs."),
            ("assistant", "Dark mode preference noted."),
        ],
        [
            ("user", "The staging environment is at staging.alpha.io."),
            ("assistant", "Staging URL: staging.alpha.io."),
        ],
        [
            ("user", "Maximum container memory is 2GB."),
            ("assistant", "Container memory limit set to 2GB."),
        ],
        [
            ("user", "We use pytest for all Python testing."),
            ("assistant", "pytest is your testing framework of choice."),
        ],
    ],
    ("tenant-alpha", "user-bob"): [
        [
            ("user", "I mostly write TypeScript."),
            ("assistant", "TypeScript is your main language."),
        ],
        [
            ("user", "We deploy on AWS EKS clusters."),
            ("assistant", "Deployments use AWS EKS."),
        ],
        [
            ("user", "My project is called Orion."),
            ("assistant", "You're working on project Orion."),
        ],
        [
            ("user", "Use Vitest for frontend tests."),
            ("assistant", "Vitest is the frontend testing tool."),
        ],
        [
            ("user", "Our API gateway is Kong."),
            ("assistant", "Kong handles API gateway duties."),
        ],
        [
            ("user", "I prefer VS Code with Vim keybindings."),
            ("assistant", "VS Code + Vim keybindings noted."),
        ],
        [
            ("user", "Max request timeout is 30 seconds."),
            ("assistant", "Request timeout ceiling: 30s."),
        ],
        [
            ("user", "We use MongoDB for the analytics service."),
            ("assistant", "Analytics service runs on MongoDB."),
        ],
        [
            ("user", "Feature flags managed by LaunchDarkly."),
            ("assistant", "LaunchDarkly handles feature flags."),
        ],
        [
            ("user", "Logging goes to Datadog."),
            ("assistant", "Datadog is the logging destination."),
        ],
    ],
    ("tenant-beta", "user-alice"): [
        [
            ("user", "I'm a data scientist, mainly use R and Julia."),
            ("assistant", "R and Julia are your primary languages."),
        ],
        [
            ("user", "Our data warehouse is Snowflake."),
            ("assistant", "Snowflake is the data warehouse."),
        ],
        [
            ("user", "I'm working on project Phoenix."),
            ("assistant", "Your current project is Phoenix."),
        ],
        [
            ("user", "We run experiments in Jupyter notebooks."),
            ("assistant", "Jupyter notebooks for experiments."),
        ],
        [
            ("user", "Model training happens on GCP with TPUs."),
            ("assistant", "Model training: GCP + TPUs."),
        ],
        [
            ("user", "MLflow tracks all experiments."),
            ("assistant", "MLflow is the experiment tracker."),
        ],
        [
            ("user", "Preferred visualization library is Plotly."),
            ("assistant", "Plotly for visualizations."),
        ],
        [
            ("user", "Data pipelines built with Apache Airflow."),
            ("assistant", "Airflow handles data pipelines."),
        ],
        [
            ("user", "Feature store is on Feast."),
            ("assistant", "Feast is the feature store."),
        ],
        [
            ("user", "Our ML models serve via Seldon Core."),
            ("assistant", "Seldon Core for model serving."),
        ],
    ],
    ("tenant-beta", "user-bob"): [
        [
            ("user", "I'm a DevOps engineer, expertise in Terraform."),
            ("assistant", "Terraform is your IaC tool of choice."),
        ],
        [
            ("user", "Infrastructure runs on Azure."),
            ("assistant", "Azure is the cloud platform."),
        ],
        [
            ("user", "Project codename is Atlas."),
            ("assistant", "Current project: Atlas."),
        ],
        [
            ("user", "We use Ansible for configuration management."),
            ("assistant", "Ansible for config management."),
        ],
        [
            ("user", "Monitoring stack is Prometheus + Grafana."),
            ("assistant", "Prometheus + Grafana for monitoring."),
        ],
        [
            ("user", "Secrets managed by HashiCorp Vault."),
            ("assistant", "Vault handles secrets."),
        ],
        [
            ("user", "Container orchestration via Nomad."),
            ("assistant", "Nomad for container orchestration."),
        ],
        [
            ("user", "DNS managed through Cloudflare."),
            ("assistant", "Cloudflare handles DNS."),
        ],
        [
            ("user", "Backup strategy: daily snapshots to S3."),
            ("assistant", "Daily backups to S3."),
        ],
        [
            ("user", "Incident management through PagerDuty."),
            ("assistant", "PagerDuty for incidents."),
        ],
    ],
}

# Queries for cross-tenant isolation testing.
# Each entry: (tenant_id, user_id, query, expected_contains, must_not_contain)
ISOLATION_QUERIES = [
    (
        "tenant-alpha", "user-alice",
        "What programming language do I prefer?",
        ["Python"],
        ["TypeScript", "R", "Julia", "Terraform"],
    ),
    (
        "tenant-alpha", "user-bob",
        "What language do I write?",
        ["TypeScript"],
        ["Python", "R", "Julia", "Terraform"],
    ),
    (
        "tenant-beta", "user-alice",
        "What languages do I use?",
        ["R", "Julia"],
        ["Python", "TypeScript", "Terraform"],
    ),
    (
        "tenant-beta", "user-bob",
        "What is my expertise?",
        ["Terraform"],
        ["Python", "TypeScript", "R", "Julia"],
    ),
    (
        "tenant-alpha", "user-alice",
        "What project am I working on?",
        ["Nebula"],
        ["Orion", "Phoenix", "Atlas"],
    ),
    (
        "tenant-alpha", "user-bob",
        "What is my project called?",
        ["Orion"],
        ["Nebula", "Phoenix", "Atlas"],
    ),
    (
        "tenant-beta", "user-alice",
        "What is my current project?",
        ["Phoenix"],
        ["Nebula", "Orion", "Atlas"],
    ),
    (
        "tenant-beta", "user-bob",
        "What project am I on?",
        ["Atlas"],
        ["Nebula", "Orion", "Phoenix"],
    ),
]
