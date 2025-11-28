# Project Imara - Testing Guide for Render Deployment

This guide will help you test every feature after deploying to Render.

---

## Step 1: Deploy to Render

### 1.1 Push to GitHub
```bash
git add .
git commit -m "Production ready"
git push origin main
```

### 1.2 Create Render Web Service
1. Go to [render.com](https://render.com) and sign in
2. Click "New" > "Web Service"
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` configuration

### 1.3 Add Environment Variables in Render Dashboard
Go to your service > Environment > Add the following:

| Variable | Value |
|----------|-------|
| `SESSION_SECRET` | Generate a random string (e.g., use an online generator) |
| `DATABASE_URL` | Your Neon PostgreSQL connection string |
| `GROQ_API_KEY` | Your Groq API key |
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `BREVO_API_KEY` | Your Brevo API key |
| `BREVO_SENDER_EMAIL` | `nwokikeonyeka@gmail.com` |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `DEBUG` | `False` |

### 1.4 Deploy
Click "Deploy" and wait for the build to complete (usually 2-5 minutes).

---

## Step 2: Basic Connectivity Tests

### 2.1 Home Page Test
- Open your Render URL (e.g., `https://project-imara.onrender.com`)
- **Expected**: Landing page loads with "Report Online Violence Securely" heading
- **Check**: Logo appears, navigation works, dark mode toggle works

### 2.2 Report Form Test
- Click "Report Now" or go to `/report/`
- **Expected**: Report form loads with text area, file upload buttons

### 2.3 Admin Panel Test
- Go to `/admin/`
- Login with:
  - Username: `Maikel`
  - Password: `Maikel1@`
- **Expected**: Django admin dashboard loads
- **Check**: You can see "Authority Contacts", "Incident Reports", "Dispatch Logs"

### 2.4 Health Check Test
- Go to `/health/`
- **Expected**: Returns "OK" or health status

---

## Step 3: Feature Tests

### Test A: Low-Risk Message (ADVISE Flow)
This tests the AI's ability to recognize low-risk situations and give advice.

1. Go to `/report/`
2. In "Message or Description", paste:
   ```
   Someone called me stupid on Facebook. It made me feel bad.
   ```
3. Click "Submit Report"
4. **Expected Result**:
   - Risk Score: 1-6 (low/moderate)
   - Action: "ADVISE"
   - You receive blocking tips and advice
   - NO email is sent to authorities

### Test B: High-Risk Message (REPORT Flow)
This tests the automatic escalation to authorities.

1. Go to `/report/`
2. In "Message or Description", paste:
   ```
   A man from Lagos posted my home address and phone number on Twitter and said he's coming to hurt me tonight. I'm scared for my life.
   ```
3. Click "Submit Report"
4. **Expected Result**:
   - Risk Score: 7-10 (high/critical)
   - Action: "REPORT"
   - Message says it was escalated to authorities
   - Email is sent to the Nigeria authority contact

### Test C: Verify Email Dispatch
After Test B:
1. Go to Admin Panel > Dispatch Logs
2. **Expected**: You see a new entry with:
   - Status: "sent"
   - Recipient email (Nigerian authority)
   - Case ID
   - Timestamp

### Test D: Screenshot Upload Test
1. Take a screenshot of an abusive message (or use a test image)
2. Go to `/report/`
3. Upload the image using "Upload Screenshot"
4. Add optional description
5. Click "Submit Report"
6. **Expected Result**:
   - AI extracts text from the image (OCR)
   - Risk assessment provided
   - Appropriate action (ADVISE or REPORT)

### Test E: Location Detection
1. Submit a report mentioning a specific country:
   ```
   Someone in Nairobi, Kenya is threatening to release my private photos.
   ```
2. **Expected**: 
   - Location detected as "Kenya" or "Nairobi"
   - If high-risk, email goes to Kenya GBV Helpline

---

## Step 4: Admin Panel Checks

### 4.1 Verify Authority Contacts
1. Go to Admin > Directory > Authority Contacts
2. **Expected**: 19+ contacts from:
   - Kenya (3)
   - Uganda (3)
   - Tanzania (3)
   - South Africa (3)
   - Nigeria (3)
   - Ghana (3)
   - Rwanda (1)

### 4.2 View Incident Reports
1. Go to Admin > Cases > Incident Reports
2. **Expected**: See your test submissions with:
   - Case ID
   - Risk Score
   - Action (advise/report)
   - AI Analysis
   - Chain Hash (SHA-256)

### 4.3 Check Dispatch Logs
1. Go to Admin > Dispatch > Dispatch Logs
2. **Expected**: See email dispatch records with status

---

## Step 5: PWA Tests

### 5.1 Service Worker
1. Open browser DevTools (F12)
2. Go to Application > Service Workers
3. **Expected**: Service worker registered

### 5.2 Install App
1. On mobile, open the site
2. Look for "Add to Home Screen" option
3. **Expected**: App installs like a native app

### 5.3 Offline Page
1. Disconnect internet
2. Try to access the site
3. **Expected**: Offline page appears (not browser error)

---

## Step 6: Telegram Bot Test (Optional)

### 6.1 Set Webhook
Run this command (replace YOUR_RENDER_URL):
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://YOUR_RENDER_URL/webhook/telegram/"
```

### 6.2 Test Commands
1. Open Telegram and find your bot
2. Send `/start` - Should get welcome message
3. Send `/help` - Should get help information
4. Forward an abusive message - Should get AI analysis

---

## Step 7: Security Verification

### 7.1 HTTPS Check
- Your Render URL should start with `https://`
- No mixed content warnings in browser

### 7.2 Headers Check
Use [securityheaders.com](https://securityheaders.com) to scan your site:
- **Expected**: Good security headers score

---

## Troubleshooting

### Issue: Site shows error 500
- Check Render logs for errors
- Verify all environment variables are set
- Make sure DATABASE_URL is correct

### Issue: Emails not sending
- Verify BREVO_API_KEY is correct
- Check BREVO_SENDER_EMAIL is verified in Brevo
- Check Dispatch Logs in admin for error messages

### Issue: AI not analyzing
- Verify GROQ_API_KEY is correct
- Verify GEMINI_API_KEY is correct
- Check Render logs for API errors

### Issue: Admin login fails
- Database might need migration
- Run: `python manage.py migrate` in Render shell
- Or recreate superuser in Render shell

---

## Quick Test Checklist

| Test | Status |
|------|--------|
| Home page loads | [ ] |
| Report form loads | [ ] |
| Admin login works | [ ] |
| Low-risk message returns ADVISE | [ ] |
| High-risk message returns REPORT | [ ] |
| Email sent to authority | [ ] |
| Screenshot upload works | [ ] |
| Location detection works | [ ] |
| Authority contacts visible in admin | [ ] |
| Incident reports logged | [ ] |
| Dispatch logs recorded | [ ] |
| Dark mode toggle works | [ ] |
| PWA installable | [ ] |

---

## Support

If something doesn't work:
1. Check Render logs (Dashboard > Logs)
2. Verify environment variables
3. Test the feature on Replit first to isolate the issue

Good luck with your launch!
