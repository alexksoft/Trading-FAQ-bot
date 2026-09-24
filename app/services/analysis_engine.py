# app/services/analysis_engine.py
# Deterministic setup analysis via a guided question flow + decision tree.
# NO AI/LLM used here — pure rule-based logic.

import logging
from app.services.session_store import get_session, save_session

logger = logging.getLogger(__name__)

CANCEL_COMMANDS = {"cancel", "stop", "exit", "quit", "reset"}

# The questions asked in order
ANALYSIS_STEPS = [
    ("asset",           "What asset are you analyzing? (e.g. BTC/USD, AAPL, EUR/USD)"),
    ("timeframe",       "What timeframe? (e.g. 1h, 4h, daily, weekly)"),
    ("entry",           "What is your planned entry price?"),
    ("stop",            "What is your stop-loss price?"),
    ("take_profit",     "What is your take-profit target?"),
    ("rsi",             "What is the current RSI value? (0-100, or type 'skip')"),
    ("price_vs_ema200", "Is price ABOVE or BELOW the 200 EMA? (type 'above', 'below', or 'skip')"),
    ("volume_trend",    "Is volume RISING, DECLINING, or FLAT? (or type 'skip')"),
    ("near_sr",         "Is price near a key support or resistance level? (type 'support', 'resistance', 'both', 'no', or 'skip')"),
]


def is_analysis_command(text: str) -> bool:
    """Return True if the user wants to start analysis mode."""
    t = text.strip().lower()
    return t in {"analyze", "analysis", "analyze setup", "start analysis", "analysis mode", "explain this setup", "explain setup"}


def handle_analysis_flow(sender: str, text: str) -> str:
    """
    Handle one step of the analysis conversation.
    Returns the next prompt or the final interpretation.
    """
    session = get_session(sender)

    # Allow cancelling at any point
    if text.strip().lower() in CANCEL_COMMANDS:
        session.mode = "bot"
        session.step = 0
        session.inputs = {}
        save_session(session)
        return "Analysis cancelled. Ask a question or type \"menu\" for topics."

    current_step = session.step

    # Starting fresh (step 0)
    if current_step == 0:
        session.mode = "analysis"
        session.step = 1
        session.inputs = {}
        save_session(session)
        return (
            "📈 *Setup Analysis Mode*\n\n"
            "I'll ask you a few questions about your setup, then describe its "
            "characteristics. I won't tell you to buy or sell — just what the "
            "indicators suggest.\n\n"
            "Type \"cancel\" anytime to exit.\n\n"
            + ANALYSIS_STEPS[0][1]
        )

    # Collecting answer for step (current_step - 1)
    step_index = current_step - 1
    field_name, _ = ANALYSIS_STEPS[step_index]

    # Validate and save the input
    value = _validate_input(field_name, text)
    if value is None:
        # Re-ask the same question with a hint
        return f"I didn't understand that. {ANALYSIS_STEPS[step_index][1]}"

    session.inputs[field_name] = value
    next_step = current_step + 1

    if next_step <= len(ANALYSIS_STEPS):
        session.step = next_step
        save_session(session)
        return ANALYSIS_STEPS[next_step - 1][1]
    else:
        # All inputs collected — run the decision tree
        session.mode = "bot"
        session.step = 0
        save_session(session)
        return _interpret(session.inputs)


def _validate_input(field: str, text: str) -> str | None:
    """
    Validate user input for a specific field.
    Returns the cleaned value, or None if invalid.
    """
    t = text.strip().lower()

    # These fields accept "skip"
    skippable = {"rsi", "price_vs_ema200", "volume_trend", "near_sr"}
    if field in skippable and t == "skip":
        return "skip"

    if field in ("asset", "timeframe"):
        # Accept any non-empty text
        return text.strip() if text.strip() else None

    if field in ("entry", "stop", "take_profit"):
        # Must be a number
        try:
            val = float(text.strip().replace(",", "").replace("$", ""))
            return str(val)
        except ValueError:
            return None

    if field == "rsi":
        try:
            val = float(t)
            if 0 <= val <= 100:
                return str(val)
            return None
        except ValueError:
            return None

    if field == "price_vs_ema200":
        if t in ("above", "below"):
            return t
        return None

    if field == "volume_trend":
        if t in ("rising", "declining", "flat"):
            return t
        return None

    if field == "near_sr":
        if t in ("support", "resistance", "both", "no"):
            return t
        return None

    return text.strip() or None


def _interpret(inputs: dict) -> str:
    """
    Run the decision tree on collected inputs.
    Returns a structured, non-directive interpretation.
    """
    asset = inputs.get("asset", "the asset")
    timeframe = inputs.get("timeframe", "your timeframe")
    rsi = inputs.get("rsi", "skip")
    ema = inputs.get("price_vs_ema200", "skip")
    volume = inputs.get("volume_trend", "skip")
    near_sr = inputs.get("near_sr", "skip")

    # Calculate risk/reward if we have the numbers
    rr_text = ""
    try:
        entry = float(inputs.get("entry", 0))
        stop = float(inputs.get("stop", 0))
        tp = float(inputs.get("take_profit", 0))
        if entry and stop and tp and abs(entry - stop) > 0:
            risk = abs(entry - stop)
            reward = abs(tp - entry)
            rr = reward / risk
            rr_text = f"\n📐 *Risk/Reward:* {rr:.1f}:1 (risk ${risk:.4f}, reward ${reward:.4f})"
    except Exception:
        pass

    # Build the interpretation piece by piece
    lines = [f"📊 *Setup Analysis: {asset} ({timeframe})*\n"]

    # RSI interpretation
    if rsi != "skip":
        rsi_val = float(rsi)
        if rsi_val < 30:
            lines.append(f"🔵 *RSI {rsi_val:.0f}* — Oversold condition. Selling pressure has been strong. "
                         f"This is a condition to watch, not an automatic buy signal.")
        elif rsi_val > 70:
            lines.append(f"🔴 *RSI {rsi_val:.0f}* — Overbought condition. Buying pressure has been strong. "
                         f"In a strong trend this can persist; needs confirmation to act on.")
        elif rsi_val > 50:
            lines.append(f"🟢 *RSI {rsi_val:.0f}* — Momentum is above the midline, suggesting buyers "
                         f"are broadly in control.")
        else:
            lines.append(f"🟡 *RSI {rsi_val:.0f}* — Momentum is below the midline, suggesting sellers "
                         f"are broadly in control.")

    # EMA 200 context
    if ema != "skip":
        if ema == "above":
            lines.append("📈 *Trend context:* Price is above the 200 EMA — long-term backdrop is bullish. "
                         "Dip-buy setups have stronger structural support here.")
        else:
            lines.append("📉 *Trend context:* Price is below the 200 EMA — long-term backdrop is bearish. "
                         "Reversal setups face headwinds from the larger trend.")

    # Volume
    if volume != "skip":
        if volume == "rising":
            lines.append("📊 *Volume:* Rising — participation is increasing, which adds conviction "
                         "to the current move.")
        elif volume == "declining":
            lines.append("📊 *Volume:* Declining — participation is fading, which weakens the "
                         "current move and raises fakeout risk.")
        else:
            lines.append("📊 *Volume:* Flat — neutral participation, no strong confirmation either way.")

    # Support/Resistance
    if near_sr != "skip":
        if near_sr == "support":
            lines.append("🧱 *Level:* Price is near a support zone — a potential area where buyers "
                         "have previously stepped in.")
        elif near_sr == "resistance":
            lines.append("🧱 *Level:* Price is near a resistance zone — a potential area where sellers "
                         "have previously stepped in.")
        elif near_sr == "both":
            lines.append("🧱 *Level:* Price is between support and resistance — in a range. "
                         "Watch for a breakout in either direction.")
        else:
            lines.append("🧱 *Level:* No key level nearby — price is in open space.")

    # Risk/reward
    if rr_text:
        lines.append(rr_text)

    # Summary and disclaimer
    lines.append(
        "\n⚠️ *Remember:* No single indicator predicts the future. "
        "Look for confluence (multiple signals agreeing) and wait for confirmation "
        "before acting. This is educational analysis, not a buy/sell recommendation.\n\n"
        "Type \"mentor\" if you'd like a human to review this setup with you."
    )

    return "\n".join(lines)
