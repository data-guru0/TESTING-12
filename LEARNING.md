# Project Learning Order

## 1. Big Picture

* **Problem Statement and What you will Learn**
* **ARCHITECTURE.mmd**


---

## 2. Infrastructure

* **bootstrap.bat / bootstrap.sh**
* **terraform/main.tf**

---

## 3. App Folder — in this order

* **requirements.txt**
* **app/config.py** — settings first, everything depends on this
* **app/retry.py** — simple utility
* **app/pool.py** — DB connection
* **app/auth.py** — API key check
* **app/guardrails.py** — Bedrock safety
* **app/cache.py** — semantic cache
* **app/memory.py** — session + LTM + embeddings
* **app/queue.py** — Redis Streams job queue
* **app/agents.py** — LangGraph 4-agent pipeline (the main brain)
* **app/eval.py** — LangSmith evaluation
* **app/output.py** — PDF, JSON, diff
* **app/main.py** — FastAPI, ties everything together
* **app/Dockerfile**

---

## 4. TensorZero — LLM Gateway

* **tensorzero/tensorzero.toml**
* **tensorzero/templates/research_summarize_system.minijinja**
* **tensorzero/templates/report_write_system.minijinja**
* **tensorzero/Dockerfile**

---

## 5. Frontend

* **index.html**

---

## 6. Red Team

* **pyrit_dashboard/main.py**
* **pyrit_dashboard/requirements.txt**
* **pyrit_dashboard/Dockerfile**

---

## 7. Github Push

**gitignore**
**gitattributes**

---

## 8. CI/CD

* **.github/workflows/deploy.yml**

## 9. Deployment Starts