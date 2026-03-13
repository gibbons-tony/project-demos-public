# Dedicated Twilio Number Setup

Upgrade from sandbox to a dedicated WhatsApp number for cleaner demo experience.

## Why Upgrade?

**Sandbox Flow (Current):**
1. User scans QR code
2. WhatsApp opens with "join manner-telephone"
3. User taps Send
4. Gets Coffee recommendation

**Dedicated Number Flow:**
1. User scans QR code
2. WhatsApp opens with "coffee"
3. User taps Send
4. Gets Coffee recommendation

**Benefit:** No "join" step - cleaner for demos/presentations

## Cost

- **Phone Number:** ~$1.00-$2.00/month (depends on country)
- **WhatsApp Setup:** One-time $0 (included with number)
- **Messages:** Same pricing as sandbox during development
- **Total:** ~$2/month

## Step 1: Purchase Twilio Number (5 min)

1. **Log in to Twilio Console**
   - https://console.twilio.com

2. **Buy a Phone Number**
   - Left sidebar → **Phone Numbers** → **Manage** → **Buy a number**
   - Filters:
     - Country: United States (or your preference)
     - Capabilities: Check **SMS** and **MMS**
   - Click **Search**

3. **Select a Number**
   - Pick any available number
   - Click **Buy** (confirms monthly cost)
   - Click **Buy This Number** to confirm

4. **Save Your Number**
   - Copy the number (e.g., `+1 415 123 4567`)
   - You'll need this for Step 3

## Step 2: Enable WhatsApp on Your Number (10 min)

### 2.1 Request WhatsApp Sender

1. In Twilio Console → **Messaging** → **Senders** → **WhatsApp senders**
2. Click **+ New WhatsApp Sender**
3. Select **I have a Twilio phone number I want to enable for WhatsApp**
4. Select your newly purchased number from dropdown
5. Click **Continue**

### 2.2 Complete WhatsApp Setup

1. **Sender Display Name:**
   - Enter: "Caramanta Coffee Advisor" (or your preference)
   - This appears in WhatsApp conversation header

2. **Business Profile:**
   - Business Description: "AI-powered coffee trading recommendations"
   - Category: Financial Services
   - Website: (optional)

3. **Message Templates:**
   - Skip for now (only needed for proactive messages)
   - Click **Skip** or **Continue**

4. **Submit for Review:**
   - Twilio will activate your number (usually instant for development)
   - Wait for "Approved" status (should be immediate)

### 2.3 Configure Webhook

1. Still in WhatsApp senders → Click your number
2. Under **Messaging Configuration:**
   - **When a message comes in:**
     - Webhook URL: `https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook`
     - Method: **POST**
   - Click **Save**

**Get your webhook URL:**
```bash
cd trading_agent/whatsapp
# It's in the deploy output, or check API Gateway console
aws apigatewayv2 get-apis --query 'Items[?Name==`trading-recommendations-api`].ApiEndpoint' --output text
```

## Step 3: Update QR Code Generator (2 min)

Create a simpler QR code that doesn't require join code:

```bash
cd trading_agent/whatsapp

# Generate QR code with your new number (no join code!)
python3 generate_qr_code_enhanced.py \
  --twilio-number "+14151234567" \
  --message "coffee" \
  --output whatsapp_demo_qr_dedicated.png
```

Or create a simple script:

```python
#!/usr/bin/env python3
"""Generate QR code for dedicated Twilio number (no join code needed)"""
import qrcode
from urllib.parse import quote

# Your dedicated Twilio number
TWILIO_NUMBER = "+14151234567"  # ← UPDATE THIS

# Pre-fill message (user just taps Send)
message = "coffee"

# Generate WhatsApp link
clean_number = TWILIO_NUMBER.replace("+", "").replace("-", "").replace(" ", "")
encoded_message = quote(message)
link = f"https://wa.me/{clean_number}?text={encoded_message}"

# Generate QR code
qr = qrcode.QRCode(version=1, box_size=10, border=4)
qr.add_data(link)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
img.save("whatsapp_demo_qr_dedicated.png")

print(f"✓ QR code saved to: whatsapp_demo_qr_dedicated.png")
print(f"✓ WhatsApp link: {link}")
print()
print("User flow:")
print("  1. Scan QR code")
print("  2. WhatsApp opens with 'coffee' pre-filled")
print("  3. Tap Send")
print("  4. Receive Coffee recommendation")
```

## Step 4: Test Your Setup (2 min)

### Test 1: Direct Message
1. Open WhatsApp on your phone
2. Send message to your new number: `coffee`
3. Should receive Coffee recommendation (same as sandbox)

### Test 2: QR Code
1. Open `whatsapp_demo_qr_dedicated.png` on another device/print it
2. Scan with your phone camera
3. WhatsApp opens with "coffee" pre-filled
4. Tap **Send**
5. Should receive Coffee recommendation

### Test 3: Lambda Logs
```bash
aws logs tail /aws/lambda/berkeley-datasci210-capstone-processor \
  --region us-west-2 --since 5m --follow
```

Should see:
```
[INFO] Received webhook request
[INFO] Message body: coffee
[INFO] [1/4] Querying current market price...
[INFO] [2/4] Calculating 7-day trend...
[INFO] [3/4] Loading forecast data...
[INFO] [4/4] Generating recommendation...
[INFO] Successfully generated recommendation for Coffee
```

## Troubleshooting

### "Message failed to send"

**Check webhook configuration:**
1. Twilio Console → Your WhatsApp sender
2. Verify webhook URL is correct
3. Verify Method is **POST**

**Test webhook directly:**
```bash
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp:+15555551234"
```

### "Number not enabled for WhatsApp"

1. Check status: Twilio Console → WhatsApp senders
2. Should show "Approved" (not "Pending")
3. If pending, wait 5-10 minutes or contact Twilio support

### QR code doesn't open WhatsApp

- Make sure phone number includes country code (e.g., `+1` for US)
- Test the direct link in a browser first
- Some phones require WhatsApp app to be installed

## Deactivating Sandbox (Optional)

Once dedicated number is working, you can deactivate the sandbox:

1. Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Click **Sandbox Settings**
3. Remove webhook URL (leave blank)
4. This prevents accidental messages to sandbox

You can always re-enable it later for testing.

## Next Steps

### For Demo/Presentation
- Share `whatsapp_demo_qr_dedicated.png` with audience
- No need to explain "join codes" - just "scan and send"
- Cleaner, more professional experience

### For Production (Future)
If you need to scale beyond development:
- WhatsApp Business API ($150+/month for 1000+ users)
- Template message approval (for proactive messages)
- Business verification

But for capstone demos and small-scale testing, dedicated Twilio number is perfect.

## Cost Comparison

| Setup | Monthly Cost | User Experience |
|-------|--------------|-----------------|
| Sandbox | FREE | Scan → Send "join code" → Send "coffee" |
| Dedicated Number | ~$2/month | Scan → Send "coffee" |
| Business API | ~$150/month | Scan → Auto-send (with templates) |

**For capstone project:** Dedicated number is the sweet spot.

## Files to Update

After setup, update your documentation:
- `README.md` - Update phone number and remove join code references
- `QUICKSTART.md` - Simplify Step 2 (no join code)
- QR code images - Regenerate with new number

## Support

**Twilio Support:**
- Console: https://console.twilio.com
- Docs: https://www.twilio.com/docs/whatsapp
- Support: Chat in console (bottom-right)

**Common Issues:**
- "Number already in use": Number was previously enabled, contact Twilio support
- "Webhook timeout": Increase Lambda timeout to 60s
- "No response": Check CloudWatch logs for Lambda errors
