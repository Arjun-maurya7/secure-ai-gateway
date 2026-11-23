from gliner import GLiNER
import torch


MODEL_ID = "urchade/gliner_multi_pii-v1"

model = GLiNER.from_pretrained(MODEL_ID)

if torch.cuda.is_available():
    model = model.to("cuda")

test_cases = [
    (
        "Clear PII",
        """
        My name is Rahul Sharma. My email is rahul.sharma@gmail.com.
        You can call me at +91 9876543210.
        My PAN is ABCDE1234F and my card number is 4111111111111111.
        """
    ),
    (
        "Ambiguous values",
        """
        Please contact Rahul regarding the account.
        The customer ID is 9876543210.
        The product code is ABCDE1234F.
        The reference number is 4111111111111111.
        """
    ),
    (
        "Mixed contextual data",
        """
        Rahul submitted the application yesterday.
        The transaction was processed from 192.168.1.10.
        Visit https://example.com for documentation.
        Contact support if you need help.
        """
    ),
    (
        "Negative cases",
        """
        The temperature is 9876543210.
        The product code is ABCDE1234F.
        The documentation is available online.
        """
    ),
]

labels = [
    "person",
    "email",
    "phone number",
    "PAN",
    "credit card number",
    "bank account number",
    "IP address",
    "API key",
    "JWT",
    "URL",
]

print("\nDetected entities:")
print("-" * 60)

for case_name, text in test_cases:
    print("\n" + "=" * 70)
    print(f"TEST CASE: {case_name}")
    print("=" * 70)
    print(f"Text: {text.strip()}")

    entities = model.predict_entities(
        text,
        labels,
        threshold=0.3,
    )

    if not entities:
        print("\nNo entities detected.")
        continue

    print("\nDetected entities:")

    for entity in entities:
        print(
            f"  Type:       {entity['label']}\n"
            f"  Value:      {entity['text']}\n"
            f"  Confidence: {entity['score']:.4f}\n"
            f"  Start:      {entity['start']}\n"
            f"  End:        {entity['end']}\n"
        )