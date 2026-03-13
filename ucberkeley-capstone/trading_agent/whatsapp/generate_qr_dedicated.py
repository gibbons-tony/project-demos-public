#!/usr/bin/env python3
"""
Generate QR Code for Dedicated Twilio WhatsApp Number (No Join Code)

Creates a QR code that opens WhatsApp with a pre-filled message.
User just needs to tap "Send" once to get recommendation.

Usage:
    python generate_qr_dedicated.py --number "+14151234567" --message "coffee"
"""

import argparse
import qrcode
from urllib.parse import quote


def generate_qr_code(phone_number: str, message: str = "coffee", output_file: str = "whatsapp_qr_dedicated.png"):
    """
    Generate QR code for dedicated WhatsApp number.

    Args:
        phone_number: Your Twilio WhatsApp number (e.g., "+14151234567")
        message: Pre-filled message (default: "coffee")
        output_file: Output PNG file path
    """
    # Remove any formatting from phone number
    clean_number = phone_number.replace("+", "").replace("-", "").replace(" ", "")

    # WhatsApp click-to-chat link format
    # https://wa.me/<number>?text=<message>
    encoded_message = quote(message)
    link = f"https://wa.me/{clean_number}?text={encoded_message}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(link)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_file)

    return link


def main():
    parser = argparse.ArgumentParser(
        description="Generate WhatsApp QR code for dedicated Twilio number (no join code)"
    )
    parser.add_argument(
        "--number",
        required=True,
        help="Your dedicated Twilio WhatsApp number (e.g., +14151234567)"
    )
    parser.add_argument(
        "--message",
        default="coffee",
        help="Pre-filled message (default: coffee)"
    )
    parser.add_argument(
        "--output",
        default="whatsapp_qr_dedicated.png",
        help="Output file path (default: whatsapp_qr_dedicated.png)"
    )

    args = parser.parse_args()

    # Generate QR code
    link = generate_qr_code(
        phone_number=args.number,
        message=args.message,
        output_file=args.output
    )

    print("=" * 70)
    print("WhatsApp QR Code Generator - Dedicated Number (No Join Code)")
    print("=" * 70)
    print()
    print(f"Phone Number: {args.number}")
    print(f"Pre-filled Message: {args.message}")
    print(f"Output File: {args.output}")
    print()
    print("WhatsApp Link:")
    print(f"  {link}")
    print()
    print("=" * 70)
    print("User Flow")
    print("=" * 70)
    print()
    print("1. User scans QR code with phone camera")
    print("2. WhatsApp opens with pre-filled message:", f'"{args.message}"')
    print("3. User taps Send")
    print("4. User receives Coffee/Sugar recommendation immediately")
    print()
    print("No 'join code' required - much cleaner for demos!")
    print()
    print("=" * 70)
    print("Next Steps")
    print("=" * 70)
    print()
    print(f"1. Display or print: {args.output}")
    print("2. Test by scanning with your phone")
    print("3. Verify you receive recommendation")
    print()
    print("For setup instructions, see: DEDICATED_NUMBER_SETUP.md")
    print()


if __name__ == "__main__":
    main()
