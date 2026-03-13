# WhatsApp Trading Bot - Sandbox Ready for Testing

## Status: Ready to Test

The WhatsApp Trading Bot sandbox is deployed and working correctly. All message flows have been verified through Lambda testing.

## Quick Start

1. Open WhatsApp on your phone
2. Scan the QR code: `whatsapp_demo_qr.png`
3. WhatsApp opens with pre-filled message: "join manner-telephone"
4. Tap "SEND"
5. You'll receive a Coffee market recommendation with real-time data

## QR Code

Location: `whatsapp_demo_qr.png` (24KB)

Features:
- Pre-fills WhatsApp with "join manner-telephone"
- Professional layout with step-by-step instructions
- WhatsApp green "TAP SEND" button
- Ready to print or display on screen

## Message Flows (All Verified)

### 1. Join Flow - Auto Coffee Welcome
**User sends:** `join manner-telephone` (via QR code)
**Bot responds:** Coffee market recommendation with:
- Current price: $3,930/ton
- 7-day trend: -6.6%
- 14-day forecast: $2,984-$3,150/ton
- Trading recommendation: SELL NOW
- Expected value analysis

**Lambda code:** lines 810-814 in lambda_handler_real.py

### 2. Coffee Request
**User sends:** `coffee`
**Bot responds:** Latest Coffee market recommendation with real Databricks data

**Lambda code:** lines 747-750 in lambda_handler_real.py

### 3. Sugar Request
**User sends:** `sugar`
**Bot responds:** Latest Sugar market recommendation with real Databricks data

**Lambda code:** lines 747-748 in lambda_handler_real.py

### 4. Exit Command
**User sends:** `exit` (or stop, quit, unsubscribe, leave, cancel)
**Bot responds:**
```
Thanks for using GroundTruth Trading! You won't receive further updates.

Message 'coffee' or 'sugar' anytime to get new recommendations.
```

**Lambda code:** lines 742-744, 820-823 in lambda_handler_real.py

### 5. Unrecognized Message - Help
**User sends:** `hello` (or any unrecognized text)
**Bot responds:**
```
Welcome to GroundTruth Trading!

Message:
  'coffee' - Coffee market recommendation
  'sugar' - Sugar market recommendation

Powered by real-time GDELT analysis
```

**Lambda code:** lines 752-753, 825-828 in lambda_handler_real.py

## Technical Details

### Lambda Function
- **Name:** berkeley-datasci210-capstone-processor
- **Region:** us-west-2
- **Package Size:** 19MB (includes requests, numpy, etc.)
- **Status:** Deployed and tested

### Twilio WhatsApp
- **Number:** +1 415 523 8886
- **Join Code:** manner-telephone
- **Type:** Sandbox (free testing)

### Data Source
- **Databricks REST API:** Real-time market data
- **Tables:** groundtruth_capstone.gold.forecast_recommendations
- **Commodities:** Coffee, Sugar
- **Forecast Horizon:** 14 days
- **Strategy:** ExpectedValue (buy/hold/sell)

## Testing Checklist

- [x] QR code generated with correct join code
- [x] Lambda deployed with all dependencies
- [x] Join flow auto-sends Coffee recommendation
- [x] Exit command sends goodbye message
- [x] Unrecognized messages show help
- [ ] Real WhatsApp end-to-end test (ready for you to try!)

## Next Steps

### Test with Real WhatsApp:
1. Open WhatsApp on your phone
2. Scan `whatsapp_demo_qr.png`
3. Tap "SEND" to join
4. Verify you receive Coffee recommendation
5. Try commands: `sugar`, `coffee`, `exit`, `hello`

### If Issues Occur:
Check Lambda logs:
```bash
AWS_PROFILE=ucberkeley-sso aws logs tail /aws/lambda/berkeley-datasci210-capstone-processor \
  --region us-west-2 --since 5m --follow
```

### Future: Production Upgrade
Once sandbox testing is complete and you're ready for production:

**Option 1: Dedicated Twilio Number (~$1/month)**
- No "join manner-telephone" requirement
- Users just scan QR and get immediate recommendation
- Cleaner UX for demos/presentations
- Keep same Lambda backend

**Option 2: WhatsApp Business API**
- Official business account
- Custom branding
- Higher rate limits
- More expensive ($$$)

**Recommendation:** Start with dedicated Twilio number for cleaner demo experience.

## Files

| File | Purpose | Size |
|------|---------|------|
| `whatsapp_demo_qr.png` | QR code for demo | 24KB |
| `lambda_handler_real.py` | Lambda function code | - |
| `trading_strategies.py` | Trading logic | - |
| `generate_qr_code_enhanced.py` | QR code generator | - |
| `/tmp/lambda-whatsapp-build-manual/lambda_function.zip` | Deployment package | 19MB |

## Support

- Twilio Console: https://console.twilio.com/
- Check Lambda logs for debugging
- Test messages manually via Twilio console if needed
