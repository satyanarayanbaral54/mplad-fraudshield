"""NLP and UC-text risk analysis for MPLAD fraud detection."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None

logger = logging.getLogger(__name__)

VAGUE_PHRASES = [
    "work completed as per norms",
    "funds utilized properly",
    "expenditure incurred as sanctioned",
    "work done as required",
    "as per government guidelines",
    "satisfactory progress",
    "work is in progress as planned",
    "completed to satisfaction",
    "utilized as per plan",
    "work executed properly",
]

SPECIFIC_INDICATORS = [
    "km",
    "meter",
    "sqm",
    "MT",
    "cubic",
    "litre",
    "quantity",
    "verified by",
    "inspected on",
    "DM office",
    "measured",
    "contractor name",
    "completion certificate",
]

FRAUD_KEYWORDS = [
    "duplicate", "ghost", "inflated", "fabricated", "substandard",
    "kickback", "bribery", "corruption", "misappropriated", "siphoned",
    "benami", "shell company", "fictitious", "collusion", "rigged",
]

POSITIVE_KEYWORDS = ["excellent", "good", "quality", "completed", "satisfied", "transparent"]
NEGATIVE_KEYWORDS = ["delay", "poor", "incomplete", "fraud", "bribe", "missing", "broken"]


def simple_sentiment(text: str) -> float:
    """Naive lexicon-based sentiment: returns score in [-1, 1]."""
    if not text:
        return 0.0
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_KEYWORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_KEYWORDS if w in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


class NLPRiskEngine:
    """UC-risk and duplicate text detection engine for MPLAD project reviews."""

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def compute_vagueness_score(self, text: str) -> Tuple[float, List[str]]:
        """Return (score 0-100, matched vague phrases)."""
        normalized = self._normalize_text(text)
        if not normalized:
            return 0.0, []

        lower_text = normalized.lower()
        matched_phrases = [phrase for phrase in VAGUE_PHRASES if phrase.lower() in lower_text]
        score = min(15 * len(matched_phrases), 60)

        words = normalized.split()
        word_count = len(words)
        if word_count < 50:
            score += 20
        if word_count < 100 and not any(ind.lower() in lower_text for ind in SPECIFIC_INDICATORS):
            score += 10

        specific_hits = [ind for ind in SPECIFIC_INDICATORS if ind.lower() in lower_text]
        score -= 5 * len(specific_hits)

        return max(0.0, min(100.0, float(score))), matched_phrases

    def detect_template_reuse(self, texts: List[str]) -> List[float]:
        """For each text, return max cosine similarity with any other text."""
        if not texts:
            return []

        valid_positions: List[int] = []
        valid_texts: List[str] = []
        for idx, text in enumerate(texts):
            cleaned = self._normalize_text(text)
            if cleaned:
                valid_positions.append(idx)
                valid_texts.append(cleaned)

        if len(valid_texts) <= 1:
            return [0.0 for _ in texts]

        vectorizer = TfidfVectorizer(ngram_range=(2, 4), min_df=1)
        tfidf_matrix = vectorizer.fit_transform(valid_texts)
        similarity_matrix = cosine_similarity(tfidf_matrix)

        results = [0.0 for _ in texts]
        for row_index, original_index in enumerate(valid_positions):
            row = similarity_matrix[row_index].copy()
            row[row_index] = 0.0
            max_similarity = float(row.max()) if row.size else 0.0
            results[original_index] = round(max_similarity, 4)

        return results

    def analyze_with_gemini(self, uc_text: str, project_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a high-risk UC via Gemini API and return a JSON-safe result."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY/GOOGLE_API_KEY is not set; skipping Gemini UC analysis.")
            return {"assessment": "ANALYSIS_FAILED", "reason": "API key missing"}

        if genai is None:
            logger.warning("google-generativeai is not installed; skipping Gemini UC analysis.")
            return {"assessment": "ANALYSIS_FAILED", "reason": "API client unavailable"}

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            work_type = project_context.get("work_type", "Unknown")
            state = project_context.get("state", "Unknown")
            amount = project_context.get("amount", project_context.get("sanctioned_amount", 0))
            days = project_context.get("days", project_context.get("days_to_completion", 0))
            clean_text = self._normalize_text(uc_text)

            prompt = (
                "You are a senior government auditor reviewing a Utilization Certificate (UC)\n"
                "for an MPLAD scheme project. The project details are:\n"
                f"Work Type: {work_type}, State: {state}, Amount: ₹{amount} Lakhs\n"
                f"Sanction to Completion: {days} days\n\n"
                f"UC Text: {clean_text}\n\n"
                "Analyze this UC and respond ONLY with valid JSON:\n"
                "{\n"
                "  'specificity_score': <0-100>,\n"
                "  'red_flags': [<list of suspicious phrases or omissions>],\n"
                "  'assessment': <'CLEAN'|'SUSPICIOUS'|'HIGHLY_SUSPICIOUS'>,\n"
                "  'reason': '<one sentence explanation>'\n"
                "}"
            )

            response = model.generate_content(prompt)
            raw_text = getattr(response, "text", "")
            if not raw_text:
                raw_text = str(response)

            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text, flags=re.IGNORECASE)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

            parsed = json.loads(cleaned_text)
            assessment = str(parsed.get("assessment", "SUSPICIOUS")).upper()
            if assessment not in {"CLEAN", "SUSPICIOUS", "HIGHLY_SUSPICIOUS"}:
                assessment = "SUSPICIOUS"

            return {
                "specificity_score": int(parsed.get("specificity_score", 0)),
                "red_flags": parsed.get("red_flags", []),
                "assessment": assessment,
                "reason": parsed.get("reason", "Review completed by Gemini."),
            }
        except Exception as exc:  # pragma: no cover - network or rate limit errors
            logger.exception("Gemini UC analysis failed: %s", exc)
            return {"assessment": "ANALYSIS_FAILED", "reason": "API error"}

    def analyze_project_texts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add vagueness, template-reuse, NLP risk, and Gemini outputs to a DataFrame."""
        if df.empty:
            return df.copy()

        result = df.copy()
        if "uc_text" not in result.columns:
            return result

        uc_texts = [self._normalize_text(text) for text in result["uc_text"].fillna("").astype(str).tolist()]
        vague_scores = []
        for text in uc_texts:
            score, _ = self.compute_vagueness_score(text)
            vague_scores.append(score)

        similarity_scores = self.detect_template_reuse(uc_texts)
        nlp_risk_scores = [0.6 * vagueness + 0.4 * (similarity * 100) for vagueness, similarity in zip(vague_scores, similarity_scores)]

        result["vagueness_score"] = vague_scores
        result["uc_similarity_score"] = similarity_scores
        result["nlp_risk_score"] = nlp_risk_scores
        result["gemini_assessment"] = "NOT_RUN"
        result["gemini_flags"] = None

        if not any(uc_text.strip() for uc_text in uc_texts):
            return result

        for idx, row in result.iterrows():
            final_risk_score = row.get("final_risk_score")
            uc_text = str(row.get("uc_text", "")).strip()
            if not uc_text or final_risk_score is None:
                continue
            try:
                if float(final_risk_score) > 50:
                    project_context = {
                        "work_type": row.get("work_type", "Unknown"),
                        "state": row.get("state", "Unknown"),
                        "amount": row.get("sanctioned_amount", row.get("allocated_amount", 0)),
                        "days": row.get("days_to_completion", row.get("duration_days", 0)),
                    }
                    gemini_result = self.analyze_with_gemini(uc_text, project_context)
                    result.at[idx, "gemini_assessment"] = gemini_result.get("assessment", "ANALYSIS_FAILED")
                    result.at[idx, "gemini_flags"] = gemini_result.get("red_flags", [])
            except (TypeError, ValueError):
                continue

        return result


class NLPEngine(NLPRiskEngine):
    """Backward-compatible NLP engine exposing simple description and survey analysis."""

    def analyze_description(self, description: str) -> Dict[str, Any]:
        """Extract fraud signals from project description text."""
        if not description:
            return {"fraud_keywords_found": [], "risk_boost": 0.0, "flags": []}

        text_lower = description.lower()
        found = [kw for kw in FRAUD_KEYWORDS if kw in text_lower]
        risk_boost = min(len(found) * 0.1, 0.5)

        flags: List[Dict[str, Any]] = []
        if found:
            flags.append({
                "flag_type": "NLP_FRAUD_KEYWORDS",
                "severity": "HIGH" if len(found) >= 3 else "MEDIUM",
                "description": f"Project description contains suspicious keywords: {', '.join(found)}.",
                "engine_source": "NLPEngine",
                "evidence": {"keywords_found": found, "risk_boost": risk_boost},
            })

        return {
            "fraud_keywords_found": found,
            "risk_boost": risk_boost,
            "flags": flags,
        }

    def analyze_survey_comment(self, comment: str) -> Dict[str, Any]:
        """Analyze citizen survey comments for sentiment and fraud signals."""
        if not comment:
            return {"sentiment_score": 0.0, "fraud_signals": [], "flags": []}

        sentiment = simple_sentiment(comment)
        fraud_signals = [kw for kw in FRAUD_KEYWORDS if kw in comment.lower()]

        flags: List[Dict[str, Any]] = []
        if sentiment < -0.3 or fraud_signals:
            flags.append({
                "flag_type": "NEGATIVE_SURVEY_SENTIMENT",
                "severity": "MEDIUM",
                "description": f"Citizen survey indicates issues. Sentiment={sentiment:.2f}.",
                "engine_source": "NLPEngine",
                "evidence": {
                    "sentiment_score": sentiment,
                    "fraud_signals": fraud_signals,
                    "comment_snippet": comment[:200],
                },
            })

        return {
            "sentiment_score": sentiment,
            "fraud_signals": fraud_signals,
            "flags": flags,
        }


nlp_risk_engine = NLPRiskEngine()
nlp_engine = NLPEngine()
