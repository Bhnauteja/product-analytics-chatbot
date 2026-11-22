"""
Multi-Provider LLM Client.
Supports:
1. Google Gemini (via GEMINI_API_KEY)
2. Anthropic Claude (via ANTHROPIC_API_KEY)
3. OpenAI (via OPENAI_API_KEY)
4. Local Ollama (100% on-premises, zero external network leakage)
5. Deterministic Mock (for local testing, CI/CD, and offline demos)
"""

import os
import json
import re
from typing import Any, Dict, Optional
import requests

class LLMClientError(Exception):
    pass

class LLMClient:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

    def generate_sql(self, prompt: str) -> Dict[str, Any]:
        """
        Sends the prompt to the configured LLM and extracts the JSON object with SQL.
        Returns:
            {"sql": str, "needs_clarification": bool, "clarifying_question": Optional[str]}
        """
        if self.provider == "gemini":
            raw_text = self._call_gemini(prompt)
        elif self.provider == "anthropic":
            raw_text = self._call_anthropic(prompt)
        elif self.provider == "openai":
            raw_text = self._call_openai(prompt)
        elif self.provider == "ollama":
            raw_text = self._call_ollama(prompt)
        elif self.provider == "mock":
            return self._call_mock(prompt)
        else:
            raise LLMClientError(f"Unsupported LLM provider: {self.provider}")

        return self._extract_json(raw_text)

    def generate_insight(self, prompt: str) -> str:
        """
        Generates 1 to 3 sentences summarizing the analytical finding.
        """
        if self.provider == "gemini":
            return self._call_gemini(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "ollama":
            return self._call_ollama(prompt)
        else:
            return self._mock_insight(prompt)

    def _call_gemini(self, prompt: str) -> str:
        if not self.gemini_key:
            raise LLMClientError("GEMINI_API_KEY is not set.")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            raise LLMClientError(f"Gemini API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise LLMClientError("Failed to parse Gemini response.")

    def _call_anthropic(self, prompt: str) -> str:
        if not self.anthropic_key:
            raise LLMClientError("ANTHROPIC_API_KEY is not set.")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": 1024,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            raise LLMClientError(f"Anthropic API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError):
            raise LLMClientError("Failed to parse Anthropic response.")

    def _call_openai(self, prompt: str) -> str:
        if not self.openai_key:
            raise LLMClientError("OPENAI_API_KEY is not set.")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            raise LLMClientError(f"OpenAI API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise LLMClientError("Failed to parse OpenAI response.")

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.ollama_base}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                raise LLMClientError(f"Ollama API error ({resp.status_code}): {resp.text}")
            return resp.json().get("response", "")
        except requests.exceptions.RequestException as e:
            raise LLMClientError(f"Failed to connect to local Ollama server at {self.ollama_base}: {str(e)}")

    def _call_mock(self, prompt: str) -> Dict[str, Any]:
        """
        Deterministic mock mode mapping common query patterns to verified SQL.
        Guarantees offline testing and zero-cost local iteration.
        """
        # Extract user question from prompt if present
        q_match = re.search(r'USER QUESTION:\s*"(.*?)"', prompt, re.DOTALL)
        target = q_match.group(1).lower() if q_match else prompt.lower()

        # 1. Daily active users
        if "daily active" in target or "dau" in target:
            return {
                "sql": "SELECT date_trunc('day', event_timestamp) AS day, COUNT(DISTINCT user_id) AS active_users FROM events WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days' GROUP BY 1 ORDER BY 1 ASC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 2. Signups this quarter
        if "quarter" in target:
            return {
                "sql": "SELECT date_trunc('week', signup_date) AS week, COUNT(*) AS signups FROM users WHERE signup_date >= date_trunc('quarter', CURRENT_DATE) GROUP BY 1 ORDER BY 1 ASC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 3. Weekly signups / trend
        if "weekly signup" in target or "signups per week" in target or "last 3 months" in target:
            return {
                "sql": "SELECT date_trunc('week', signup_date) AS week, COUNT(*) AS signups FROM users WHERE signup_date >= CURRENT_DATE - INTERVAL '90 days' GROUP BY 1 ORDER BY 1 ASC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 4. Top countries
        if "country" in target or "countries" in target:
            return {
                "sql": "SELECT country, COUNT(*) AS signups FROM users WHERE signup_date >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month' AND signup_date < date_trunc('month', CURRENT_DATE) GROUP BY country ORDER BY signups DESC LIMIT 5;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 5. Top products by revenue
        if "product" in target:
            return {
                "sql": "SELECT p.name AS product_name, ROUND(SUM(o.amount), 2) AS total_revenue FROM orders o JOIN products p ON o.product_id = p.product_id WHERE o.status = 'completed' GROUP BY p.name ORDER BY total_revenue DESC LIMIT 10;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 6. Acquisition channels
        if "channel" in target:
            return {
                "sql": "SELECT acquisition_channel, COUNT(*) AS user_count FROM users GROUP BY acquisition_channel ORDER BY user_count DESC LIMIT 10;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 7. Funnel / drop-off
        if "drop off" in target or "funnel" in target or "checkout" in target:
            return {
                "sql": "SELECT event_type AS funnel_step, COUNT(DISTINCT user_id) AS unique_users FROM events WHERE event_type IN ('visit', 'add_to_cart', 'checkout_start', 'purchase') GROUP BY event_type ORDER BY CASE event_type WHEN 'visit' THEN 1 WHEN 'add_to_cart' THEN 2 WHEN 'checkout_start' THEN 3 WHEN 'purchase' THEN 4 ELSE 5 END ASC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 8. Conversion rate / cart to purchase
        if "conversion rate" in target or "cart to purchase" in target:
            return {
                "sql": "SELECT COUNT(DISTINCT CASE WHEN event_type = 'add_to_cart' THEN user_id END) AS cart_users, COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchasers, ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) / NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'add_to_cart' THEN user_id END), 0), 2) AS conversion_rate_pct FROM events WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days' LIMIT 1;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 9. Retention / cohorts
        if "retention" in target or "cohort" in target:
            return {
                "sql": "WITH cohort_users AS (SELECT user_id, date_trunc('month', signup_date) AS signup_cohort FROM users WHERE signup_date >= CURRENT_DATE - INTERVAL '6 months'), week1_activity AS (SELECT DISTINCT e.user_id, c.signup_cohort FROM events e JOIN cohort_users c ON e.user_id = c.user_id JOIN users u ON u.user_id = c.user_id WHERE e.event_timestamp >= u.signup_date + INTERVAL '7 days' AND e.event_timestamp < u.signup_date + INTERVAL '14 days') SELECT c.signup_cohort::VARCHAR AS signup_cohort, COUNT(DISTINCT c.user_id) AS cohort_size, COUNT(DISTINCT w.user_id) AS retained_users, ROUND(100.0 * COUNT(DISTINCT w.user_id) / NULLIF(COUNT(DISTINCT c.user_id), 0), 2) AS retention_rate_pct FROM cohort_users c LEFT JOIN week1_activity w ON c.user_id = w.user_id AND c.signup_cohort = w.signup_cohort GROUP BY 1 ORDER BY 1 ASC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 10. Mobile vs desktop
        if "mobile vs desktop" in target or "compare mobile" in target:
            return {
                "sql": "SELECT platform, COUNT(DISTINCT user_id) AS total_visitors, COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchasers, ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate_pct FROM events WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days' GROUP BY platform ORDER BY conversion_rate_pct DESC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 11. Revenue by device
        if "device" in target:
            return {
                "sql": "SELECT u.device, COUNT(DISTINCT o.order_id) AS completed_orders, ROUND(SUM(o.amount), 2) AS total_revenue FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.status = 'completed' GROUP BY u.device ORDER BY total_revenue DESC LIMIT 1000;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 12. Plan breakdown
        if "plan" in target:
            return {
                "sql": "SELECT plan, COUNT(*) AS user_count FROM users GROUP BY plan ORDER BY user_count DESC LIMIT 10;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # 13. Total revenue / KPI
        if "total revenue" in target or "how much revenue" in target or "sales" in target:
            return {
                "sql": "SELECT ROUND(SUM(amount), 2) AS total_revenue FROM orders WHERE status = 'completed' LIMIT 1;",
                "needs_clarification": False,
                "clarifying_question": None
            }

        # Generic default
        return {
            "sql": "SELECT plan, COUNT(*) AS user_count FROM users GROUP BY plan ORDER BY user_count DESC LIMIT 10;",
            "needs_clarification": False,
            "clarifying_question": None
        }

    def _mock_insight(self, prompt: str) -> str:
        return "Based on the queried data, key metrics indicate strong conversion performance with consistent engagement across top user segments."

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Parses JSON object from LLM response, handling markdown fences.
        """
        cleaned = text.strip()
        # Remove markdown ```json ... ``` wrapper if present
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1)
        else:
            # Try to find { ... }
            curly_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if curly_match:
                cleaned = curly_match.group(1)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback if raw SQL was returned instead of JSON
            raw_sql = text.replace("```sql", "").replace("```", "").strip()
            return {
                "sql": raw_sql,
                "needs_clarification": False,
                "clarifying_question": None
            }
