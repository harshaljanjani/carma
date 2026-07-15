DECLINE_MESSAGES = {
    "competitor": (
        "I can only help with cars in the Carma inventory, so I'm not able to discuss "
        "other brands or dealers as comparisons. Would you like to keep exploring our listings?"
    ),
    "other_platform": (
        "I'm focused on the Carma marketplace and can't speak to other used-car "
        "platforms. Happy to help you find something in our inventory, though."
    ),
    "code_writing": (
        "Writing code is outside what I do here. I'm your Carma assistant, so I can help "
        "you search listings, answer questions about them, or book a viewing."
    ),
    "non_automotive": (
        "That's a bit outside my lane. I'm here to help you explore Carma listings and "
        "book viewings. Want to tell me what kind of car you're after?"
    ),
    "history": (
        "I can't help with general knowledge or history questions. I'm your Carma "
        "assistant, so I can help you find and learn about cars in our inventory."
    ),
}

DEFAULT_DECLINE = (
    "I'm your Carma assistant, so I can help you explore our listings and book a viewing, "
    "but that request is outside what I can do."
)


def decline_for(category):
    return DECLINE_MESSAGES.get(category, DEFAULT_DECLINE)
