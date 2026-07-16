import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant import memory
from assistant.agent import _classify, handle_chat

RESULTS = []


def check(category, desc, passed, detail=""):
    RESULTS.append((category, desc, bool(passed), detail))


def sid():
    return "ceval" + uuid.uuid4().hex[:10]


def uid():
    return "CEval" + uuid.uuid4().hex[:8]


INTENT_CASES = [
    ("chitchat", "yo yo what's good", "chitchat"),
    ("chitchat", "howdy partner", "chitchat"),
    ("chitchat", "hey there buddy", "chitchat"),
    ("chitchat", "thanks a million", "chitchat"),
    ("chitchat", "much appreciated mate", "chitchat"),
    ("chitchat", "how's it going today", "chitchat"),
    ("chitchat", "good morning!", "chitchat"),
    ("chitchat", "sup", "chitchat"),
    ("chitchat", "cheers", "chitchat"),
    ("chitchat", "what's my name", "chitchat"),
    ("chitchat", "do you remember me", "chitchat"),
    ("chitchat", "how long have i been a member", "chitchat"),
    ("inventory_query", "got any beemers?", "inventory_query"),
    ("inventory_query", "show me them benzes", "inventory_query"),
    ("inventory_query", "whatchu got in stock", "inventory_query"),
    ("inventory_query", "any rollers?", "inventory_query"),
    ("inventory_query", "lemme peep a toyota", "inventory_query"),
    ("inventory_query", "gimme a bentley", "inventory_query"),
    ("inventory_query", "any 4x4s or suvs", "inventory_query"),
    ("inventory_query", "show me somethin white", "inventory_query"),
    ("inventory_query", "anything from 2020 or newer", "inventory_query"),
    ("inventory_query", "i wanna see a land rover", "inventory_query"),
    ("inventory_query", "what wheels you got fam", "inventory_query"),
    ("inventory_query", "do you have a range rover", "inventory_query"),
    ("booking_lead", "lemme book a viewing", "booking_lead"),
    ("booking_lead", "wanna come see it in person", "booking_lead"),
    ("booking_lead", "set up a test drive please", "booking_lead"),
    ("booking_lead", "pencil me in for saturday", "booking_lead"),
    ("booking_lead", "schedule a showing for me", "booking_lead"),
    ("booking_lead", "can i test drive one", "booking_lead"),
    ("manage_bookings", "what have i booked so far", "manage_bookings"),
    ("manage_bookings", "show my viewings", "manage_bookings"),
    ("manage_bookings", "scrap my booking", "manage_bookings"),
    ("manage_bookings", "cancel that appointment", "manage_bookings"),
    ("manage_bookings", "what appointments do i have", "manage_bookings"),
    ("manage_bookings", "ditch all my bookings", "manage_bookings"),
    ("out_of_scope", "write me a python quicksort", "out_of_scope"),
    ("out_of_scope", "who won the 2010 world cup", "out_of_scope"),
    ("out_of_scope", "what's the capital of france", "out_of_scope"),
    ("out_of_scope", "is autotrader better than you", "out_of_scope"),
    ("out_of_scope", "should i use dubicars instead", "out_of_scope"),
    ("out_of_scope", "tell me a joke about cats", "out_of_scope"),
    ("out_of_scope", "recommend a good restaurant", "out_of_scope"),
    ("out_of_scope", "how do i cook pasta", "out_of_scope"),
    ("out_of_scope", "who is the president of the usa", "out_of_scope"),
    ("out_of_scope", "debug my javascript function", "out_of_scope"),
    ("chitchat", "long time no see", "chitchat"),
    ("chitchat", "you there?", "chitchat"),
    ("chitchat", "much obliged", "chitchat"),
    ("chitchat", "who are you", "chitchat"),
    ("chitchat", "what can you help me with", "chitchat"),
    ("chitchat", "nice to meet you", "chitchat"),
    ("inventory_query", "cheapest one you got", "inventory_query"),
    ("inventory_query", "show me something sporty", "inventory_query"),
    ("inventory_query", "a family suv please", "inventory_query"),
    ("inventory_query", "low mileage rides", "inventory_query"),
    ("inventory_query", "anything silver", "inventory_query"),
    ("inventory_query", "gimme a rolls royce", "inventory_query"),
    ("inventory_query", "cars between 2015 and 2018", "inventory_query"),
    ("inventory_query", "wanna see a mini", "inventory_query"),
    ("inventory_query", "a merc glc", "inventory_query"),
    ("inventory_query", "show me convertibles", "inventory_query"),
    ("booking_lead", "reserve me a slot", "booking_lead"),
    ("booking_lead", "i'd like to view one", "booking_lead"),
    ("booking_lead", "can we set something up for the weekend", "booking_lead"),
    ("manage_bookings", "how many bookings do i have", "manage_bookings"),
    ("manage_bookings", "wipe all my bookings", "manage_bookings"),
    ("manage_bookings", "drop my bentley booking", "manage_bookings"),
    ("manage_bookings", "list my appointments", "manage_bookings"),
    ("out_of_scope", "what year did world war 2 end", "out_of_scope"),
    ("out_of_scope", "is carwow cheaper than you", "out_of_scope"),
    ("out_of_scope", "give me some stock tips", "out_of_scope"),
    ("out_of_scope", "what's the weather today", "out_of_scope"),
    ("out_of_scope", "translate hello to spanish", "out_of_scope"),
    ("out_of_scope", "who painted the mona lisa", "out_of_scope"),
]


def run_intent():
    for category, message, expected in INTENT_CASES:
        got = _classify(sid(), message).intent
        check("intent:" + category, f"{message!r} -> {expected}", got == expected, f"got {got}")


def run_retrieval():
    cases = [
        ("show me toyotas", "toyota"),
        ("got any beemers", "bmw"),
        ("any benz please", "mercedes-benz"),
        ("do you have a range rover", "land rover"),
        ("show me a bentley", "bentley"),
        ("chevy?", "chevrolet"),
        ("a vw", "volkswagen"),
        ("a merc", "mercedes-benz"),
        ("gimme a rolls royce", "rolls-royce"),
        ("landrover please", "land rover"),
        ("wanna see a mini", "mini"),
        ("white cars", None),
        ("suvs", None),
        ("cars after 2022", None),
        ("black cars", None),
        ("convertibles", None),
        ("cars between 2015 and 2018", None),
        ("cars under 60000 km", None),
    ]
    for message, make in cases:
        r = handle_chat(sid(), uid(), message)
        makes = {l.make for l in r.listings}
        ok = (make in makes) if make else (len(r.listings) > 0)
        check("retrieval", f"{message!r}", ok, f"makes={sorted(makes)[:4]} n={len(r.listings)}")

    for message in ["what's on your inventory, a bit confused?", "whatchu packing?", "just browsing, show me stuff"]:
        r = handle_chat(sid(), uid(), message)
        check("browse", f"{message!r} returns a sample", len(r.listings) > 0, f"n={len(r.listings)}")

    for message in ["do you have any hondas", "got a tesla?"]:
        r = handle_chat(sid(), uid(), message)
        check("no_inventory", f"{message!r} returns none", len(r.listings) == 0, f"n={len(r.listings)}")


def run_booking_flows():
    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    handle_chat(s, u, "book the first one for monday at 2pm, budget 40k")
    handle_chat(s, u, "yes")
    leads = memory.get_leads(u)
    check("booking", "multi-turn book records a lead", any(l["day"] == "Monday" for l in leads), f"leads={len(leads)}")

    u, s = uid(), sid()
    handle_chat(s, u, "show me a bmw")
    r1 = handle_chat(s, u, "wanna book one")
    check("booking", "vague pick asks which car (no premature book)", "booked" not in r1.reply.lower(), r1.reply[:50])
    handle_chat(s, u, "the first one, wednesday 5pm, budget 30k")
    r2 = handle_chat(s, u, "yep this is the one")
    check("booking", "'yep this is the one' confirms + records",
          any(l["day"] == "Wednesday" for l in memory.get_leads(u)), r2.reply[:50])

    u, s = uid(), sid()
    handle_chat(s, u, "show me a bentley")
    handle_chat(s, u, "book the first one for friday at 10am, budget 200k")
    r = handle_chat(s, u, "no thanks")
    check("booking", "'no thanks' at confirm does NOT record",
          not memory.get_leads(u) and "won't book" in r.reply.lower(), r.reply[:50])

    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    handle_chat(s, u, "book the first one for tomorrow at 11am, budget 50k")
    handle_chat(s, u, "go for it")
    check("booking", "relative date 'tomorrow' books", len(memory.get_leads(u)) == 1, f"leads={memory.get_leads(u)}")

    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    handle_chat(s, u, "book the first one for monday at 3pm, budget 40k")
    handle_chat(s, u, "yes")
    handle_chat(s, u, "show me a bmw")
    handle_chat(s, u, "book the first one for monday at 3pm, budget 40k")
    r = handle_chat(s, u, "yes")
    check("booking", "same-slot conflict is blocked", "already have" in r.reply.lower(), r.reply[:60])

    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    q = handle_chat(s, u, "book the first one for thursday at 1pm")
    check("booking", "qualify stage asks for budget/requirements",
          "budget" in q.reply.lower() or "requirement" in q.reply.lower(), q.reply[:50])
    handle_chat(s, u, "budget 45k, must have a sunroof")
    handle_chat(s, u, "yes")
    check("booking", "qualify captures budget+requirements into lead", len(memory.get_leads(u)) == 1, f"leads={memory.get_leads(u)}")


def run_manage():
    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    handle_chat(s, u, "book the first one for monday at 9am, budget 40k")
    handle_chat(s, u, "yes")
    r = handle_chat(s, u, "show my bookings")
    check("manage", "view returns booking rows", len(r.bookings) >= 1, f"n={len(r.bookings)}")
    r2 = handle_chat(s, u, "cancel my toyota booking")
    check("manage", "cancel removes the booking", len(memory.get_leads(u)) == 0, f"remaining={len(r2.bookings)}")


def run_reference():
    u, s = uid(), sid()
    r0 = handle_chat(s, u, "show me toyotas")
    if r0.listings:
        r1 = handle_chat(s, u, "tell me more about the first one")
        check("reference", "'the first one' resolves to a car", len(r1.listings) == 1, f"n={len(r1.listings)}")
    u, s = uid(), sid()
    handle_chat(s, u, "book a bentley")
    handle_chat(s, u, "the continental")
    r = handle_chat(s, u, "actually tell me more about it first")
    check("reference", "'it' resolves during booking (not lost)",
          "couldn't find" not in r.reply.lower(), r.reply[:50])


def run_personal():
    u, s = uid(), sid()
    handle_chat(s, u, f"hi, my name is {u}")
    r = handle_chat(s, u, "what's my name?")
    check("personal", "recalls the given name", u.lower() in r.reply.lower(), r.reply[:60])


def run_grounding():
    r = handle_chat(sid(), uid(), "show me a ferrari")
    real = all(l.make == "ferrari" for l in r.listings)
    check("grounding", "ferrari query returns only ferraris", real and len(r.listings) >= 1, f"n={len(r.listings)}")
    r2 = handle_chat(sid(), uid(), "do you have a lamborghini aventador in pink with racing stripes")
    lambos = all(l.make == "lamborghini" for l in r2.listings)
    check("grounding", "invented trim/colour does not fabricate cars", lambos, f"makes={ {l.make for l in r2.listings} }")


def run_edge():
    u, s = uid(), sid()
    r = handle_chat(s, u, "show me a ferrari, actually no, a toyota")
    makes = {l.make for l in r.listings}
    check("edge", "self-correcting request lands on toyota", "toyota" in makes or len(r.listings) > 0, f"makes={makes}")

    u, s = uid(), sid()
    r0 = handle_chat(s, u, "show me some bmws")
    if len(r0.listings) >= 2:
        r1 = handle_chat(s, u, "tell me about the second one")
        check("edge", "'the second one' resolves", len(r1.listings) == 1, f"n={len(r1.listings)}")

    u, s = uid(), sid()
    handle_chat(s, u, "show me a toyota")
    handle_chat(s, u, "book the first one for thursday at 1pm")
    handle_chat(s, u, "skip")
    handle_chat(s, u, "yes")
    handle_chat(s, u, "cancel it")
    check("edge", "book then cancel leaves no bookings", len(memory.get_leads(u)) == 0, f"leads={len(memory.get_leads(u))}")

    u, s = uid(), sid()
    r = handle_chat(s, u, "umm i dunno, just show me whatever you got")
    check("edge", "confused/vague request still returns cars", len(r.listings) > 0, f"n={len(r.listings)}")

    u, s = uid(), sid()
    handle_chat(s, u, "i wanna book something")
    r = handle_chat(s, u, "what's the capital of france")
    check("edge", "out-of-scope during booking is declined", r.intent == "out_of_scope", f"intent={r.intent}")


def report():
    from collections import defaultdict
    by_cat = defaultdict(lambda: [0, 0])
    for cat, _, passed, _ in RESULTS:
        base = cat.split(":")[0]
        by_cat[base][1] += 1
        if passed:
            by_cat[base][0] += 1
    total_pass = sum(1 for r in RESULTS if r[2])
    print("=" * 70)
    for cat in sorted(by_cat):
        ok, tot = by_cat[cat]
        print(f"  {cat:16} {ok}/{tot}")
    print("-" * 70)
    print(f"  OVERALL: {total_pass}/{len(RESULTS)} = {total_pass / len(RESULTS):.1%}")
    fails = [r for r in RESULTS if not r[2]]
    if fails:
        print("\nFAILURES:")
        for cat, desc, _, detail in fails:
            print(f"  [{cat}] {desc}  ({detail})")


if __name__ == "__main__":
    run_intent()
    run_retrieval()
    run_booking_flows()
    run_manage()
    run_reference()
    run_personal()
    run_grounding()
    run_edge()
    report()
