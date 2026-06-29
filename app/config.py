import os
import socket
import boto3
import json
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_secret() -> dict:
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId="research-agent/config")
    return json.loads(response["SecretString"])


class Config:
    def __init__(self):
        data = _load_secret()

        # AWS
        self.aws_region: str = data.get("AWS_REGION", "us-east-1")

        # Bedrock Guardrails
        self.bedrock_guardrail_id: str = data["BEDROCK_GUARDRAIL_ID"]
        self.bedrock_guardrail_version: str = data["BEDROCK_GUARDRAIL_VERSION"]

        # Storage
        self.redis_url: str = data["REDIS_URL"]
        self.database_url: str = data["DATABASE_URL"]
        self.tensorzero_url: str = data["TENSORZERO_URL"]

        # Auth
        self.api_key: str = data.get("API_KEY", "")

        # LangSmith tracing
        self.langsmith_api_key: str = data.get("LANGSMITH_API_KEY", "")
        self.langchain_project: str = data.get("LANGCHAIN_PROJECT", "research-agent")
        self.langsmith_dataset: str = data.get("LANGSMITH_DATASET", "research-agent-reports")

        # Semantic cache
        self.cache_ttl: int = int(data.get("CACHE_TTL", 3600))
        self.cache_similarity_threshold: float = float(data.get("CACHE_SIMILARITY_THRESHOLD", 0.85))

        # Session memory
        self.session_ttl: int = int(data.get("SESSION_TTL", 1800))
        self.session_max_messages: int = int(data.get("SESSION_MAX_MESSAGES", 5))
        self.session_content_truncate: int = int(data.get("SESSION_CONTENT_TRUNCATE", 500))

        # Long-term memory
        self.ltm_days: int = int(data.get("LTM_DAYS", 7))
        self.ltm_threshold: float = float(data.get("LTM_THRESHOLD", 0.88))
        self.ltm_diff_threshold: float = float(data.get("LTM_DIFF_THRESHOLD", 0.7))
        self.ltm_diff_limit: int = int(data.get("LTM_DIFF_LIMIT", 5))
        self.ivfflat_lists: int = int(data.get("IVFFLAT_LISTS", 100))

        # Job queue
        self.stream_key: str = data.get("STREAM_KEY", "research:jobs")
        self.consumer_group: str = data.get("CONSUMER_GROUP", "workers")
        # hostname = unique per ECS task = safe for horizontal scaling
        self.consumer_name: str = data.get("CONSUMER_NAME", socket.gethostname())
        self.result_ttl: int = int(data.get("RESULT_TTL", 3600))

        # Agent tuning
        self.agent_report_truncate: int = int(data.get("AGENT_REPORT_TRUNCATE", 3000))
        self.agent_max_iterations: int = int(data.get("AGENT_MAX_ITERATIONS", 2))

        # Eval tuning
        self.eval_report_truncate: int = int(data.get("EVAL_REPORT_TRUNCATE", 1500))
        self.eval_comment_truncate: int = int(data.get("EVAL_COMMENT_TRUNCATE", 300))

        # LLM retry
        self.llm_max_retries: int = int(data.get("LLM_MAX_RETRIES", 3))
        self.llm_retry_delay: float = float(data.get("LLM_RETRY_DELAY", 1.0))

        # Rate limiting (per IP, per window)
        self.rate_limit_requests: int = int(data.get("RATE_LIMIT_REQUESTS", 10))
        self.rate_limit_window: int = int(data.get("RATE_LIMIT_WINDOW", 60))

        # DB connection pool
        self.db_pool_min: int = int(data.get("DB_POOL_MIN", 2))
        self.db_pool_max: int = int(data.get("DB_POOL_MAX", 10))

        if self.langsmith_api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_project
            os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
