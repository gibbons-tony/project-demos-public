#!/usr/bin/env python3
"""
Generate QR Code for WhatsApp Trading Recommendations Demo

Creates a QR code that:
1. Opens WhatsApp to Twilio number
2. Pre-fills join message + commodity request
3. User just needs to tap "Send" once

Usage:
    python generate_qr_code.py --twilio-number "+14155238886" --join-code "yellow-donkey" --commodity coffee
"""

import argparse
import qrcode
from urllib.parse import quote


def generate_whatsapp_link(twilio_number: str, join_code: str, commodity: str = "coffee") -> str:
    """
    Generate WhatsApp click-to-chat link with pre-filled message.

    Args:
        twilio_number: Twilio WhatsApp number (e.g., "+14155238886")
        join_code: Your Twilio sandbox join code (e.g., "yellow-donkey")
        commodity: Default commodity to request (coffee or sugar)

    Returns:
        WhatsApp deep link URL
    """
    # Remove any formatting from phone number
    clean_number = twilio_number.replace("+", "").replace("-", "").replace(" ", "")

    # Pre-fill message: join code + commodity request
    message = f"join {join_code}"

    # For immediate recommendation, can append commodity in same message
    # Some Twilio configs might handle this, but safer to do in two messages
    # So we'll just do the join for now

    # WhatsApp click-to-chat link format
    # https://wa.me/<number>?text=<message>
    encoded_message = quote(message)
    link = f"https://wa.me/{clean_number}?text={encoded_message}"

    return link


def generate_qr_code(link: str, output_file: str = "whatsapp_qr_code.png"):
    """
    Generate QR code image from WhatsApp link.

    Args:
        link: WhatsApp deep link
        output_file: Output PNG file path
    """
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

    print(f"✓ QR code saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate WhatsApp QR code for trading recommendations demo"
    )
    parser.add_argument(
        "--twilio-number",
        required=True,
        help="Twilio WhatsApp number (e.g., +14155238886)"
    )
    parser.add_argument(
        "--join-code",
        required=True,
        help="Your Twilio sandbox join code (e.g., yellow-donkey)"
    )
    parser.add_argument(
        "--commodity",
        default="coffee",
        choices=["coffee", "sugar"],
        help="Default commodity to request (default: coffee)"
    )
    parser.add_argument(
        "--output",
        default="whatsapp_qr_code.png",
        help="Output file path (default: whatsapp_qr_code.png)"
    )

    args = parser.parse_args()

    # Generate WhatsApp link
    link = generate_whatsapp_link(
        twilio_number=args.twilio_number,
        join_code=args.join_code,
        commodity=args.commodity
    )

    print("=" * 60)
    print("WhatsApp Trading Recommendations - QR Code Generator")
    print("=" * 60)
    print()
    print(f"Twilio Number: {args.twilio_number}")
    print(f"Join Code: {args.join_code}")
    print(f"Default Commodity: {args.commodity}")
    print()
    print("WhatsApp Link:")
    print(f"  {link}")
    print()

    # Generate QR code
    generate_qr_code(link, args.output)

    print()
    print("=" * 60)
    print("How to Use")
    print("=" * 60)
    print()
    print("For Demo Participants:")
    print("  1. Scan this QR code with your phone camera")
    print("  2. Tap 'Open WhatsApp' when prompted")
    print("  3. WhatsApp opens with pre-filled join message")
    print("  4. Tap 'Send' to join the sandbox")
    print("  5. Send 'coffee' or 'sugar' to get recommendations")
    print()
    print("First-time Setup:")
    print("  - After joining, send 'coffee' to get coffee recommendations")
    print("  - Or send 'sugar' to get sugar recommendations")
    print()
    print(f"QR Code Image: {args.output}")
    print()


if __name__ == "__main__":
    main()
