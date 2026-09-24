# app/services/risk_calculator.py
# Deterministic position-size calculator. No AI/LLM used here.
# Formula: position_size = (account * risk%) / |entry - stop|

import logging
import math
import re

from app.services.session_store import get_session, save_session

logger = logging.getLogger(__name__)

# The questions asked in order during the risk calculator flow
RISK_STEPS = [
    ("account", "What is your account size? (e.g. 5000)"),
    ("risk_pct", "What % of your account do you want to risk? (e.g. 1)"),
    ("entry", "What is your entry price? (e.g. 100.50)"),
    ("stop", "What is your stop-loss price? (e.g. 95.00)"),
]

CANCEL_COMMANDS = {"cancel", "stop", "exit", "quit", "reset"}


def is_risk_command(text: str) -> bool:
    """Return True if the user wants to start the risk calculator."""
    t = text.strip().lower()
    return t in {"risk", "risk calculator", "calculate risk", "position size calculator", "risk calc"}


def handle_risk_flow(sender: str, text: str) -> str:
    """
    Handle one step of the risk calculator conversation.
    Returns the next prompt or the final result.
    """
    session = get_session(sender)

    # Allow cancelling at any point
    if text.strip().lower() in CANCEL_COMMANDS:
        session.mode = "bot"
        session.step = 0
        session.inputs = {}
        save_session(session)
        return "Risk calculator cancelled. Ask a question or type \"menu\" for topics."

    current_step = session.step

    # If we're just starting (step 0), ask the first question
    if current_step == 0:
        session.mode = "risk"
        session.step = 1
        session.inputs = {}
        save_session(session)
        return RISK_STEPS[0][1]  # "What is your account size?"

    # We're collecting an answer for step (current_step - 1)
    step_index = current_step - 1
    field_name, _ = RISK_STEPS[step_index]

    # Validate the input is a positive number
    value = _parse_number(text)
    if value is None or value <= 0:
        # Re-ask the same question
        return f"Please enter a valid positive number. {RISK_STEPS[step_index][1]}"

    # Save this input
    session.inputs[field_name] = value

    # Move to the next step
    next_step = current_step + 1

    if next_step <= len(RISK_STEPS):
        # Ask the next question
        session.step = next_step
        save_session(session)
        return RISK_STEPS[next_step - 1][1]
    else:
        # All inputs collected — calculate the result
        session.mode = "bot"
        session.step = 0
        save_session(session)
        return _calculate(session.inputs)


def _calculate(inputs: dict) -> str:
    """
    Run the position size calculation and return a formatted result.
    """
    account = inputs.get("account", 0)
    risk_pct = inputs.get("risk_pct", 0)
    entry = inputs.get("entry", 0)
    stop = inputs.get("stop", 0)

    # Validate: entry and stop must differ
    per_unit_risk = abs(entry - stop)
    if per_unit_risk == 0:
        return (
            "❌ Entry and stop-loss cannot be the same price. "
            "Type \"risk\" to try again."
        )

    # The core formula
    dollar_risk = account * (risk_pct / 100)
    position_size = math.floor(dollar_risk / per_unit_risk)

    if position_size == 0:
        return (
            f"⚠️ With these numbers, the position size rounds down to 0 units.\n"
            f"Your stop is very close to entry (${per_unit_risk:.4f} per unit) "
            f"but your dollar risk is only ${dollar_risk:.2f}.\n"
            f"Consider a wider stop or higher risk amount."
        )

    return (
        f"📊 *Position Size Calculation*\n\n"
        f"Account: ${account:,.2f}\n"
        f"Risk: {risk_pct}% = *${dollar_risk:,.2f}*\n"
        f"Entry: ${entry:,.4f}\n"
        f"Stop-loss: ${stop:,.4f}\n"
        f"Per-unit risk: |{entry} - {stop}| = *${per_unit_risk:,.4f}*\n\n"
        f"Position size = ${dollar_risk:,.2f} ÷ ${per_unit_risk:,.4f}\n"
        f"= *{position_size} units* (rounded down)\n\n"
        f"Max loss if stopped out: {position_size} × ${per_unit_risk:,.4f} = "
        f"${position_size * per_unit_risk:,.2f} ({risk_pct}% of account)\n\n"
        f"_This is educational only. Always verify your own calculations._"
    )


def _parse_number(text: str) -> float | None:
    """Extract a number from text. Returns None if not a valid number."""
    # Remove common formatting like $ , %
    cleaned = re.sub(r"[$,%]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None
