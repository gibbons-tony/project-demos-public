#!/usr/bin/env python3
"""
Generate Enhanced QR Code for WhatsApp Trading Recommendations Demo

Creates a professional QR code with instructions that:
1. Opens WhatsApp to Twilio number
2. Pre-fills custom message (join code + optional commodity)
3. Shows clear "TAP SEND" instruction
"""

import argparse
import qrcode
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote


def generate_whatsapp_link(twilio_number: str, message: str) -> str:
    """
    Generate WhatsApp click-to-chat link with pre-filled message.

    Args:
        twilio_number: Twilio WhatsApp number (e.g., "+14155238886")
        message: Custom message to pre-fill

    Returns:
        WhatsApp deep link URL
    """
    # Remove any formatting from phone number
    clean_number = twilio_number.replace("+", "").replace("-", "").replace(" ", "")

    # WhatsApp click-to-chat link format
    # https://wa.me/<number>?text=<message>
    encoded_message = quote(message)
    link = f"https://wa.me/{clean_number}?text={encoded_message}"

    return link


def generate_qr_code_with_instructions(
    link: str,
    output_file: str = "whatsapp_qr_code.png",
    title: str = "GroundTruth Trading",
    subtitle: str = "AI-Powered Commodity Recommendations"
):
    """
    Generate QR code with instructions overlay.

    Args:
        link: WhatsApp deep link
        output_file: Output PNG file path
        title: Main title text
        subtitle: Subtitle text
    """
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=12,
        border=2,
    )

    qr.add_data(link)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Convert QR code to RGB mode for compatibility
    qr_img = qr_img.convert('RGB')

    # Create new image with extra space for text
    qr_width, qr_height = qr_img.size

    # Add space for title (top), instructions (bottom), and side margins
    margin_top = 120
    margin_bottom = 180
    margin_sides = 40

    total_width = qr_width + (margin_sides * 2)
    total_height = qr_height + margin_top + margin_bottom

    # Create white background
    img = Image.new('RGB', (total_width, total_height), 'white')

    # Paste QR code in center
    qr_position = ((total_width - qr_width) // 2, margin_top)
    img.paste(qr_img, qr_position)

    # Add text
    draw = ImageDraw.Draw(img)

    # Try to use a system font, fallback to default if not available
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 32)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
        instruction_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 28)
        step_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except:
        try:
            # Try Linux font paths
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            instruction_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            step_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            # Fallback to default font
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            instruction_font = ImageFont.load_default()
            step_font = ImageFont.load_default()

    # Title at top
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (total_width - title_width) // 2
    draw.text((title_x, 20), title, fill='black', font=title_font)

    # Subtitle
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (total_width - subtitle_width) // 2
    draw.text((subtitle_x, 65), subtitle, fill='gray', font=subtitle_font)

    # Instructions at bottom
    y_offset = qr_height + margin_top + 20

    # Step 1
    step1 = "1. Scan with camera"
    step1_bbox = draw.textbbox((0, 0), step1, font=step_font)
    step1_width = step1_bbox[2] - step1_bbox[0]
    step1_x = (total_width - step1_width) // 2
    draw.text((step1_x, y_offset), step1, fill='black', font=step_font)

    # Step 2
    step2 = "2. WhatsApp opens with message"
    step2_bbox = draw.textbbox((0, 0), step2, font=step_font)
    step2_width = step2_bbox[2] - step2_bbox[0]
    step2_x = (total_width - step2_width) // 2
    draw.text((step2_x, y_offset + 30), step2, fill='black', font=step_font)

    # Step 3 - BOLD and highlighted
    step3 = "3. TAP \"SEND\" ✓"
    step3_bbox = draw.textbbox((0, 0), step3, font=instruction_font)
    step3_width = step3_bbox[2] - step3_bbox[0]
    step3_x = (total_width - step3_width) // 2

    # Add background highlight for emphasis
    padding = 10
    draw.rectangle(
        [step3_x - padding, y_offset + 60 - padding,
         step3_x + step3_width + padding, y_offset + 60 + 35 + padding],
        fill='#25D366'  # WhatsApp green
    )
    draw.text((step3_x, y_offset + 60), step3, fill='white', font=instruction_font)

    # Step 4
    step4 = "4. Get your recommendation!"
    step4_bbox = draw.textbbox((0, 0), step4, font=step_font)
    step4_width = step4_bbox[2] - step4_bbox[0]
    step4_x = (total_width - step4_width) // 2
    draw.text((step4_x, y_offset + 115), step4, fill='gray', font=step_font)

    # Save image
    img.save(output_file, quality=95)

    print(f"✓ QR code with instructions saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate WhatsApp QR code with instructions for trading recommendations demo"
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
        "--message",
        help="Custom message to pre-fill (default: 'join {code}')"
    )
    parser.add_argument(
        "--commodity",
        default=None,
        choices=["coffee", "sugar"],
        help="Add commodity request after join (e.g., 'join code\\ncoffee')"
    )
    parser.add_argument(
        "--output",
        default="whatsapp_qr_code.png",
        help="Output file path (default: whatsapp_qr_code.png)"
    )
    parser.add_argument(
        "--title",
        default="GroundTruth Trading",
        help="Title text on QR code"
    )
    parser.add_argument(
        "--subtitle",
        default="AI-Powered Commodity Recommendations",
        help="Subtitle text on QR code"
    )

    args = parser.parse_args()

    # Build message
    if args.message:
        # Use custom message
        message = args.message
    else:
        # Default: join code
        message = f"join {args.join_code}"

        # Optionally add commodity request
        # Note: Some Twilio sandboxes may not process multi-line messages correctly
        # If this doesn't work, the Lambda will send welcome message with instructions
        if args.commodity:
            message += f"\n{args.commodity}"

    # Generate WhatsApp link
    link = generate_whatsapp_link(
        twilio_number=args.twilio_number,
        message=message
    )

    print("=" * 70)
    print("WhatsApp Trading Recommendations - QR Code Generator")
    print("=" * 70)
    print()
    print(f"Twilio Number: {args.twilio_number}")
    print(f"Join Code: {args.join_code}")
    print(f"Pre-filled Message: {message}")
    print()
    print("WhatsApp Link:")
    print(f"  {link}")
    print()

    # Generate QR code with instructions
    generate_qr_code_with_instructions(
        link,
        args.output,
        title=args.title,
        subtitle=args.subtitle
    )

    print()
    print("=" * 70)
    print("QR Code Features")
    print("=" * 70)
    print()
    print("✓ Title: " + args.title)
    print("✓ Subtitle: " + args.subtitle)
    print("✓ QR Code: Opens WhatsApp with pre-filled message")
    print("✓ Highlighted instruction: 'TAP SEND' (WhatsApp green)")
    print("✓ Step-by-step guide for users")
    print()
    print(f"QR Code saved to: {args.output}")
    print()
    print("=" * 70)
    print("Usage Examples")
    print("=" * 70)
    print()
    print("# Basic (join only)")
    print(f"  ./generate_qr_code_enhanced.py --twilio-number '{args.twilio_number}' --join-code '{args.join_code}'")
    print()
    print("# Join + Coffee request")
    print(f"  ./generate_qr_code_enhanced.py --twilio-number '{args.twilio_number}' --join-code '{args.join_code}' --commodity coffee")
    print()
    print("# Custom message")
    print(f"  ./generate_qr_code_enhanced.py --twilio-number '{args.twilio_number}' --message 'Hello! Send me trading recommendations'")
    print()
    print("# Custom branding")
    print(f"  ./generate_qr_code_enhanced.py --twilio-number '{args.twilio_number}' --join-code '{args.join_code}' \\")
    print(f"    --title 'UC Berkeley MIDS' --subtitle 'Capstone Demo'")
    print()


if __name__ == "__main__":
    main()
