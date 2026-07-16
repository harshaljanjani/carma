import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.agent import _classify
from assistant.config import HAS_LLM

CASES = [
    ("hi there", "chitchat"),
    ("thanks so much", "chitchat"),
    ("how are you today", "chitchat"),
    ("show me a white toyota", "inventory_query"),
    ("do you have any bmw under 80000 km", "inventory_query"),
    ("what is the mileage on the first one", "inventory_query"),
    ("is that one still under warranty", "inventory_query"),
    ("book me a viewing on saturday at 3pm", "booking_lead"),
    ("i want to test drive the mercedes", "booking_lead"),
    ("can you schedule a viewing", "booking_lead"),
    ("write me a python script to sort a list", "out_of_scope"),
    ("who won the world cup in 1998", "out_of_scope"),
    ("what is the capital of france", "out_of_scope"),
    ("is dubicars cheaper than you", "out_of_scope"),
    ("should i buy a honda from a different dealer instead", "out_of_scope"),
    ("tell me a joke about politics", "out_of_scope"),
]


def evaluate():
    labels = sorted({c[1] for c in CASES})
    correct = 0
    per_class = {l: [0, 0] for l in labels}
    confusion = []
    for message, expected in CASES:
        got = _classify("evalsession", message).intent
        per_class[expected][1] += 1
        if got == expected:
            correct += 1
            per_class[expected][0] += 1
        else:
            confusion.append((message, expected, got))
    return correct, per_class, confusion


def report():
    correct, per_class, confusion = evaluate()
    mode = "LLM classifier" if HAS_LLM else "deterministic heuristic fallback (no GEMINI_API_KEY)"
    print(f"intent classification metric | path: {mode}")
    print(f"accuracy: {correct}/{len(CASES)} = {correct/len(CASES):.1%}")
    print("per-intent recall:")
    for label, (ok, total) in per_class.items():
        print(f"  {label:<16} {ok}/{total}")
    if confusion:
        print("misclassified:")
        for msg, exp, got in confusion:
            print(f"  {msg[:45]:<47} expected={exp:<15} got={got}")


if __name__ == "__main__":
    report()
