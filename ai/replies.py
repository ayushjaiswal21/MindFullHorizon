"""Fixed replies for the mode where no AI model reads what a student writes (AI_SEND_PERSONAL_TEXT off).

These are code, not model output. The crisis, friend and soft-risk texts stay in ai/service.py and always win."""
from utils.helplines import helplines_text

OFF_REPLY = ("Thank you for telling me. I am an automated assistant and no AI model reads what you write here, so I "
             "cannot talk it through with you. You can pick one of the saved questions above, write in your journal, "
             "or book a counsellor, who is a real person. If you feel unsafe, please reach out now: ")


def off_reply():
    """Reply to an ordinary message when personal text is not sent to a model; helplines come from the one config."""
    return OFF_REPLY + helplines_text()
