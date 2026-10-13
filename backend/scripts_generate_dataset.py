"""Generates a synthetic, template-based training set -> data/tickets.csv.

No real customer data. Deterministic (seeded). Run: python scripts_generate_dataset.py
"""
import csv
import random
from pathlib import Path

random.seed(7)

# solution -> (category, subjects, descriptions)
SPEC = {
    "Reset the password using the account recovery process.": (
        "Account",
        ["Unable to log in", "Forgot my password", "Can't sign in to my account", "Password not working", "Login keeps failing"],
        [
            "I forgot my password and cannot access my account.",
            "My password doesn't work anymore and I can't get into my account.",
            "I can't remember my login password. How do I get back in?",
            "Every time I enter my password it says incorrect. I think I forgot it.",
            "I need to change my password because I'm locked out of my profile.",
            "Lost my password, please help me regain access to my account.",
        ],
    ),
    "Verify your identity to unlock the locked account.": (
        "Account",
        ["Account locked", "Account suspended after login attempts", "My account has been blocked", "Locked out too many attempts"],
        [
            "My account says it is locked after several failed login attempts.",
            "I got a message that my account was temporarily blocked for suspicious activity.",
            "Account locked after I typed the wrong code too many times.",
            "It says my account is suspended and I need to verify something. What do I do?",
            "I'm locked out because of too many incorrect attempts and the lock isn't lifting.",
        ],
    ),
    "Update the email address from the account settings page.": (
        "Account",
        ["Change my email address", "Update email on account", "Wrong email on my profile", "Need to use a new email"],
        [
            "I changed jobs and need to switch the email on my account to a new one.",
            "My old email address is no longer active, how do I update it?",
            "I entered a typo in my email when signing up and want to correct it.",
            "Please help me change the email linked to my account.",
            "I want my notifications going to a different email address.",
        ],
    ),
    "Reconfigure two-factor authentication using your backup codes.": (
        "Account",
        ["Two-factor code not working", "Lost my phone 2FA", "Authenticator app issue", "2FA verification failing"],
        [
            "I got a new phone and my authenticator app no longer has my codes.",
            "The two-factor verification code is always rejected when I log in.",
            "I lost the phone that I use for 2FA and can't sign in.",
            "My authentication codes don't work and I can't pass the verification step.",
            "I never receive the SMS verification code for two-factor login.",
        ],
    ),
    "Request a refund for the duplicate charge through the billing portal.": (
        "Billing",
        ["Charged twice", "Duplicate payment on my card", "Double billing this month", "Refund for extra charge"],
        [
            "I was charged twice for the same order this month. Please refund one payment.",
            "I see two identical charges on my credit card statement for one subscription.",
            "My card was billed double and I need the extra amount returned.",
            "There is a duplicate transaction on my bill. How do I get my money back?",
            "I was overcharged due to a repeated payment and want a refund.",
        ],
    ),
    "Update the payment method in billing settings and retry the payment.": (
        "Billing",
        ["Payment failed", "Card declined", "Payment method expired", "Unable to complete payment"],
        [
            "My payment was declined because my card expired. How can I use a new card?",
            "The payment keeps failing even though my card is valid.",
            "I got a notice that my last payment failed and I need to update my card details.",
            "Credit card declined at checkout and I want to try a different payment method.",
            "Billing failed on my subscription renewal, please help me fix the card.",
        ],
    ),
    "Download the invoice from the billing history page.": (
        "Billing",
        ["Need invoice copy", "Where can I get my receipt", "Invoice for accounting", "Request billing statement"],
        [
            "I need a copy of last month's invoice for my accounting records.",
            "Where can I download the receipt for my recent purchase?",
            "My finance team needs a PDF invoice for our subscription payment.",
            "Please send me the invoice with the tax details for my order.",
            "I can't find my past invoices and need them for reimbursement.",
        ],
    ),
    "Cancel the subscription from the subscription tab in account settings.": (
        "Billing",
        ["Cancel my subscription", "Stop auto renewal", "How to unsubscribe", "End my plan"],
        [
            "I want to cancel my subscription before it renews next week.",
            "Please stop my plan from renewing automatically.",
            "How do I unsubscribe from the premium plan? I no longer need it.",
            "I'd like to end my membership and avoid future charges.",
            "Cancel my monthly plan, I'm switching to another service.",
        ],
    ),
    "Track the order using the tracking link in the shipping confirmation email.": (
        "Shipping",
        ["Where is my order", "Order not arrived yet", "Track my package", "Delivery taking too long"],
        [
            "I placed an order a week ago and it still hasn't arrived. Where is it?",
            "How can I check the shipping status of my package?",
            "My delivery is late and I want to know where my parcel is right now.",
            "I need the tracking number for my recent order.",
            "The estimated delivery date has passed and I haven't received anything.",
        ],
    ),
    "Start a return and request a replacement for the damaged or incorrect item.": (
        "Shipping",
        ["Received damaged item", "Wrong product delivered", "Item arrived broken", "Need to return my order"],
        [
            "The product I received was broken when I opened the box.",
            "I got a different item than what I ordered. How do I exchange it?",
            "My order arrived damaged and I would like a replacement.",
            "The package contained the wrong size and I want to return it.",
            "The item is defective and I need to send it back for a replacement.",
        ],
    ),
    "Update the delivery address before the order ships.": (
        "Shipping",
        ["Change delivery address", "Wrong shipping address", "Need to update address on order", "Send order to a different address"],
        [
            "I entered the wrong shipping address on my order. Can I change it?",
            "I moved recently and need my package sent to my new address.",
            "Please update the delivery address on my pending order.",
            "My order should go to my office instead of my home address.",
            "There's a typo in the street name of the address for my order.",
        ],
    ),
    "Clear the app cache and update to the latest app version.": (
        "Technical",
        ["App keeps crashing", "App freezes on startup", "Mobile app not loading", "App is very slow"],
        [
            "The mobile app crashes every time I open it.",
            "The app is stuck on the loading screen and never opens.",
            "Since the last update the app freezes and lags a lot.",
            "The application closes by itself right after launch.",
            "Pages in the app don't load and it shows a blank screen.",
        ],
    ),
    "Check the service status page and retry once the outage is resolved.": (
        "Technical",
        ["Service is down", "Website not loading", "Getting server error 500", "Cannot reach the platform"],
        [
            "The whole website is down and I keep getting a server error.",
            "I see a 503 error whenever I try to open the dashboard.",
            "Nothing loads for me and my teammates also can't connect to the platform.",
            "The service appears to be offline. Is there an outage?",
            "I get a timeout error on every page since this morning.",
        ],
    ),
    "Restart the device and pair it again through the app.": (
        "Technical",
        ["Device not connecting", "Cannot pair my device", "Device offline in app", "Bluetooth pairing fails"],
        [
            "My device shows offline in the app and won't reconnect.",
            "I can't pair the device over Bluetooth, it keeps failing.",
            "The device lost its connection and doesn't appear in the app anymore.",
            "After a power cut my device stopped syncing with the app.",
            "Pairing keeps timing out when I try to add my device.",
        ],
    ),
    "Submit a data deletion request through the privacy center.": (
        "Privacy",
        ["Delete my data", "Request account deletion", "Remove my personal information", "GDPR data erasure"],
        [
            "I want all of my personal data deleted from your systems.",
            "Please delete my account and everything associated with it.",
            "How can I request the erasure of my personal information under GDPR?",
            "I no longer use the service and want my data removed permanently.",
            "I'd like to know how to have my profile and history erased.",
        ],
    ),
    "Follow the getting-started guide in the help center for setup steps.": (
        "Product",
        ["How do I set up", "Need help getting started", "How to use a feature", "Setup instructions"],
        [
            "I'm new here and need help setting up my workspace.",
            "Can you explain how to use the reporting feature step by step?",
            "I can't figure out how to get started after signing up.",
            "Where can I find a guide for configuring my first project?",
            "I need a walkthrough on how to invite my team and set up permissions.",
        ],
    ),
}

PREFIXES = ["", "", "", "Hi, ", "Hello support, ", "Urgent: ", "Please help. ", "Hi team, "]
SUFFIXES = ["", "", "", " Thanks.", " Please advise.", " Thanks in advance!", " This is quite frustrating."]
PER_CLASS = 40


def main() -> None:
    rows = []
    for solution, (category, subjects, descs) in SPEC.items():
        seen = set()
        while len(seen) < min(PER_CLASS, len(subjects) * len(descs) * 4):
            s = random.choice(subjects)
            d = random.choice(descs)
            d = random.choice(PREFIXES) + d[0].lower() + d[1:] if random.random() < 0.5 else d
            d += random.choice(SUFFIXES)
            seen.add((s, d))
        rows += [(s, d, category, solution) for s, d in seen]
    random.shuffle(rows)

    out = Path(__file__).parent / "data" / "tickets.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "description", "category", "solution"])
        w.writerows(rows)
    print(f"wrote {len(rows)} rows, {len(SPEC)} classes -> {out}")


if __name__ == "__main__":
    main()
