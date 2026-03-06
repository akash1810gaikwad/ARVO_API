import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Optional, List, Dict
from utils.logger import logger

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "support@arvomobile.co.uk"
SMTP_PASSWORD = "jeyr fsui hgfq raqm"
DEFAULT_BCC = ["akg6595@gmail.com"]
IMG_URL = "https://arvomobile.co.uk"
INSTALL_ESIM_LINK = "https://esimsetup.apple.com/esim_qrcode_provisioning?carddata="


def send_email(*,
               to_email: str,
               subject: str,
               body_html: str,
               inline_images: Optional[Dict[str, bytes]] = None,
               body_text: Optional[str] = None,
               bcc: Optional[List[str]] = None) -> bool:
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    
    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    
    msg.attach(MIMEText(body_html, "html"))
    
    if inline_images:
        for cid, img_bytes in inline_images.items():
            img = MIMEImage(img_bytes, "png")
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
            msg.attach(img)
    
    recipients = [to_email] + (bcc if bcc is not None else DEFAULT_BCC)
    server = None
    
    try:
        logger.info(f"Sending email to {to_email}")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, recipients, msg.as_string())
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                pass


def get_esim_qr_email_template(child_name: str, mobile_number: str, iccid: str, qr_code: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Your ARVO eSIM QR Code</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#111;">Your eSIM QR Code is Ready</h2>
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px 20px;">
<p style="margin:5px 0; font-size:15px;"><strong>For:</strong> {child_name}</p>
<p style="margin:5px 0; font-size:15px;"><strong>Mobile Number:</strong> {mobile_number}</p>
<p style="margin:5px 0; font-size:15px;"><strong>SIM ID (ICCID):</strong> {iccid}</p>
</td>
</tr>

<tr>
<td align="center" style="padding:10px;">
<img src="cid:qr_code" width="200" height="200" alt="QR Code" style="display:block;">
<p style="font-size:12px; color:#666; margin-top:10px;"><strong>Activation Code:</strong> {qr_code}</p>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px 10px;">
<p style="font-size:14px; color:#444; margin-bottom:15px;">📱 <strong>Tap below to install your eSIM on iPhone</strong></p>
<!--[if mso]>
<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{INSTALL_ESIM_LINK+qr_code}" style="height:50px;v-text-anchor:middle;width:250px;" arcsize="12%" stroke="f" fillcolor="#000000">
<w:anchorlock/>
<center style="color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:600;">Install eSIM on iPhone</center>
</v:roundrect>
<![endif]-->
<!--[if !mso]><!-->
<table border="0" cellspacing="0" cellpadding="0">
<tr>
<td align="center" bgcolor="#000000" style="background-color:#000; border-radius:6px; padding:0;">
<a href="{INSTALL_ESIM_LINK+qr_code}" style="background-color:#000; color:#fff; padding:16px 40px; text-decoration:none; font-weight:600; display:inline-block; border-radius:6px; font-family:Arial,sans-serif;">Install eSIM on iPhone</a>
</td>
</tr>
</table>
<!--<![endif]-->
</td>
</tr>

<tr>
<td style="padding:30px 40px 20px;">
<div style="background:#f8f9fb; border-radius:8px; padding:18px;">
<h3 style="margin-top:0; font-size:16px; font-weight:600;">How to Install Your eSIM</h3>
<p style="margin:8px 0; font-size:14px;">1. Open Settings on your iPhone</p>
<p style="margin:8px 0; font-size:14px;">2. Tap Mobile Data (or Cellular)</p>
<p style="margin:8px 0; font-size:14px;">3. Select Add eSIM</p>
<p style="margin:8px 0; font-size:14px;">4. Scan the QR code above</p>
<p style="margin:8px 0; font-size:14px;">5. Follow on-screen instructions</p>
</div>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px;">
<p style="font-size:13px; color:#777;">Need help? Contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_esim_qr_email(customer_email: str, child_name: str, mobile_number: str, 
                       iccid: str, qr_code: str, qr_image_bytes: bytes) -> bool:
    """Send eSIM QR code email to customer"""
    try:
        logger.info(f"Building QR code email for {child_name} to {customer_email}")
        
        subject = f"Your e-SIM QR Code for {child_name}"
        body_html = get_esim_qr_email_template(child_name, mobile_number, iccid, qr_code)
        
        inline_images = {"qr_code": qr_image_bytes}
        
        logger.info(f"Calling send_email with subject: {subject}")
        result = send_email(
            to_email=customer_email,
            subject=subject,
            body_html=body_html,
            inline_images=inline_images
        )
        
        logger.info(f"send_email returned: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in send_esim_qr_email: {str(e)}", exc_info=True)
        return False


def get_order_confirmation_email_template(customer_name: str, order_number: str, plan_name: str, 
                                         number_of_children: int, total_amount: float, 
                                         currency: str, invoice_url: str = None) -> str:
    invoice_button = ""
    if invoice_url:
        invoice_button = f"""
<tr>
<td align="center" style="padding:20px 40px 10px;">
<!--[if mso]>
<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{invoice_url}" style="height:50px;v-text-anchor:middle;width:200px;" arcsize="12%" stroke="f" fillcolor="#000000">
<w:anchorlock/>
<center style="color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:600;">View Invoice</center>
</v:roundrect>
<![endif]-->
<!--[if !mso]><!-->
<table border="0" cellspacing="0" cellpadding="0">
<tr>
<td align="center" bgcolor="#000000" style="background-color:#000; border-radius:6px; padding:0;">
<a href="{invoice_url}" style="background-color:#000; color:#fff; padding:16px 40px; text-decoration:none; font-weight:600; display:inline-block; border-radius:6px; font-family:Arial,sans-serif;">View Invoice</a>
</td>
</tr>
</table>
<!--<![endif]-->
</td>
</tr>"""
    
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Order Confirmation - ARVO</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#111;">Order Confirmed!</h2>
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px 20px;">
<p style="margin:5px 0; font-size:15px; color:#666;">Thank you for your order, {customer_name}</p>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<div style="background:#f8f9fb; border-radius:8px; padding:20px;">
<h3 style="margin-top:0; font-size:16px; font-weight:600; color:#111;">Order Details</h3>
<table width="100%" cellpadding="5" cellspacing="0" border="0">
<tr>
<td style="font-size:14px; color:#666;">Order Number:</td>
<td style="font-size:14px; font-weight:600; color:#111; text-align:right;">{order_number}</td>
</tr>
<tr>
<td style="font-size:14px; color:#666;">Plan:</td>
<td style="font-size:14px; font-weight:600; color:#111; text-align:right;">{plan_name}</td>
</tr>
<tr>
<td style="font-size:14px; color:#666;">Number of SIMs:</td>
<td style="font-size:14px; font-weight:600; color:#111; text-align:right;">{number_of_children}</td>
</tr>
<tr>
<td style="font-size:14px; color:#666; padding-top:10px; border-top:1px solid #ddd;">Total Amount:</td>
<td style="font-size:16px; font-weight:700; color:#111; text-align:right; padding-top:10px; border-top:1px solid #ddd;">{currency.upper()} {total_amount:.2f}</td>
</tr>
</table>
</div>
</td>
</tr>

{invoice_button}

<tr>
<td style="padding:20px 40px;">
<div style="background:#fff3cd; border-left:4px solid:#ffc107; border-radius:4px; padding:15px;">
<p style="margin:0; font-size:14px; color:#856404;"><strong>📧 Check Your Email</strong></p>
<p style="margin:8px 0 0 0; font-size:13px; color:#856404;">You will receive separate emails with QR codes for each SIM card. Please check your inbox.</p>
</div>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<h3 style="margin-top:0; font-size:16px; font-weight:600;">What's Next?</h3>
<p style="margin:8px 0; font-size:14px; color:#444;">1. Check your email for individual QR codes for each SIM</p>
<p style="margin:8px 0; font-size:14px; color:#444;">2. Scan the QR code on your device to activate the eSIM</p>
<p style="margin:8px 0; font-size:14px; color:#444;">3. Follow the on-screen instructions to complete setup</p>
<p style="margin:8px 0; font-size:14px; color:#444;">4. Start using your ARVO mobile service!</p>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px;">
<p style="font-size:13px; color:#777;">Need help? Contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_order_confirmation_email(customer_email: str, customer_name: str, order_number: str,
                                  plan_name: str, number_of_children: int, total_amount: float,
                                  currency: str, invoice_url: str = None) -> bool:
    """Send order confirmation email with optional Stripe invoice link"""
    try:
        logger.info(f"Sending order confirmation email to {customer_email}")
        
        subject = f"Order Confirmation - {order_number}"
        body_html = get_order_confirmation_email_template(
            customer_name, order_number, plan_name, number_of_children,
            total_amount, currency, invoice_url
        )
        
        result = send_email(
            to_email=customer_email,
            subject=subject,
            body_html=body_html
        )
        
        logger.info(f"Order confirmation email result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {str(e)}", exc_info=True)
        return False


def get_welcome_email_template(customer_name: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Welcome to ARVO</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 30px 20px;">
<h1 style="margin:0; font-size:30px; font-weight:700; color:#111;">Welcome to ARVO</h1>
</td>
</tr>

<tr>
<td style="padding:0 40px 10px;">
<p style="font-size:18px; font-weight:600; color:#111; margin:0;">Hi {customer_name},</p>
</td>
</tr>

<tr>
<td style="padding:15px 40px 10px;">
<p style="font-size:15px; color:#444; line-height:26px;">Thank you for registering with ARVO! We're excited to have you join our community.</p>

<p style="font-size:15px; color:#444; line-height:26px;">With ARVO, you can:</p>

<ul style="padding-left:20px; color:#444; font-size:15px; line-height:28px;">
<li>Manage your family's mobile connectivity</li>
<li>Choose flexible subscription plans</li>
<li>Get eSIM or physical SIM cards for your children</li>
<li>Track usage and manage subscriptions easily</li>
</ul>

<p style="font-size:15px; color:#444; line-height:26px; margin-top:25px;">Ready to get started? Log in to your account and explore our plans.</p>
</td>
</tr>

<tr>
<td align="center" style="padding:20px 30px 40px;">
<!--[if mso]>
<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{IMG_URL}" style="height:50px;v-text-anchor:middle;width:200px;" arcsize="12%" stroke="f" fillcolor="#000000">
<w:anchorlock/>
<center style="color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:600;">Get Started</center>
</v:roundrect>
<![endif]-->
<!--[if !mso]><!-->
<table border="0" cellspacing="0" cellpadding="0">
<tr>
<td align="center" bgcolor="#000000" style="background-color:#000; border-radius:6px; padding:0;">
<a href="{IMG_URL}" style="background-color:#000; color:#fff; text-decoration:none; padding:16px 45px; font-size:16px; font-weight:600; display:inline-block; border-radius:6px; font-family:Arial,sans-serif;">Get Started</a>
</td>
</tr>
</table>
<!--<![endif]-->
</td>
</tr>

<tr>
<td align="center">
<div style="width:80%; height:1px; background:#eeeeee;"></div>
</td>
</tr>

<tr>
<td align="center" style="padding:25px 30px 40px;">
<p style="font-size:13px; color:#777; margin:5px 0;">If you have any questions, feel free to contact our support team.</p>
<p style="font-size:13px; color:#777; margin:5px 0;">Email: <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_welcome_email(customer_email: str, customer_name: str) -> bool:
    from config.mysql_database import MySQLSessionLocal
    from services.email_template_service import email_template_service
    
    subject = "Welcome to ARVO - Let's Get Started!"
    body_html = get_welcome_email_template(customer_name)
    body_text = f"""Welcome to ARVO!

Hi {customer_name},

Thank you for registering with ARVO! We're excited to have you join our community.

With ARVO, you can:
- Manage your family's mobile connectivity
- Choose flexible subscription plans
- Get eSIM or physical SIM cards for your children
- Track usage and manage subscriptions easily

Ready to get started? Log in to your account and explore our plans.

If you have any questions, contact us at support@arvomobile.co.uk

Best regards,
The ARVO Team"""
    
    try:
        db = MySQLSessionLocal()
        template = email_template_service.get_template_by_key(db, "welcome_email")
        if template:
            subject, body_html, body_text = email_template_service.render_template(
                template,
                {"customer_name": customer_name}
            )
            logger.info("Using welcome email template from database")
        db.close()
    except Exception as e:
        logger.warning(f"Could not load template from database, using default: {str(e)}")
    
    return send_email(
        to_email=customer_email,
        subject=subject,
        body_html=body_html,
        body_text=body_text
    )



def get_complaint_created_email_template(customer_name: str, complaint_number: str, 
                                         complaint_title: str, complaint_description: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Complaint Received</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#111;">Complaint Received</h2>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:16px; color:#111; margin:0 0 10px;">Hi {customer_name},</p>
<p style="font-size:15px; color:#444; line-height:24px;">Thank you for contacting us. We have received your complaint and our team will review it shortly.</p>
</td>
</tr>

<tr>
<td style="padding:10px 40px;">
<div style="background:#f8f9fb; border-radius:8px; padding:20px;">
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Complaint Number:</strong></p>
<p style="margin:0 0 15px; font-size:18px; color:#000; font-weight:600;">{complaint_number}</p>
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Subject:</strong></p>
<p style="margin:0 0 15px; font-size:15px; color:#111;">{complaint_title}</p>
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Description:</strong></p>
<p style="margin:0; font-size:14px; color:#444; line-height:22px;">{complaint_description}</p>
</div>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:14px; color:#444; line-height:24px;">We aim to resolve your complaint as quickly as possible. You will receive an update once our team has reviewed your case.</p>
<p style="font-size:14px; color:#444; line-height:24px; margin-top:15px;">Please keep your complaint number for reference.</p>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px;">
<p style="font-size:13px; color:#777;">Need immediate assistance? Contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_complaint_created_email(customer_email: str, customer_name: str, 
                                 complaint_number: str, complaint_title: str, 
                                 complaint_description: str) -> bool:
    subject = f"Complaint Received - {complaint_number}"
    body_html = get_complaint_created_email_template(
        customer_name, complaint_number, complaint_title, complaint_description
    )
    
    return send_email(
        to_email=customer_email,
        subject=subject,
        body_html=body_html
    )


def get_complaint_resolved_email_template(customer_name: str, complaint_number: str, 
                                         complaint_title: str, resolution_notes: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Complaint Resolved</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#28a745;">Complaint Resolved</h2>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:16px; color:#111; margin:0 0 10px;">Hi {customer_name},</p>
<p style="font-size:15px; color:#444; line-height:24px;">Good news! Your complaint has been resolved by our team.</p>
</td>
</tr>

<tr>
<td style="padding:10px 40px;">
<div style="background:#f8f9fb; border-radius:8px; padding:20px;">
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Complaint Number:</strong></p>
<p style="margin:0 0 15px; font-size:18px; color:#000; font-weight:600;">{complaint_number}</p>
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Subject:</strong></p>
<p style="margin:0 0 15px; font-size:15px; color:#111;">{complaint_title}</p>
<p style="margin:0 0 8px; font-size:14px; color:#666;"><strong>Resolution:</strong></p>
<p style="margin:0; font-size:14px; color:#444; line-height:22px;">{resolution_notes}</p>
</div>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:14px; color:#444; line-height:24px;">We hope this resolves your issue. If you have any further questions or concerns, please don't hesitate to contact us.</p>
<p style="font-size:14px; color:#444; line-height:24px; margin-top:15px;">Thank you for your patience and for choosing ARVO.</p>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px;">
<p style="font-size:13px; color:#777;">Questions? Contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_complaint_resolved_email(customer_email: str, customer_name: str, 
                                  complaint_number: str, complaint_title: str, 
                                  resolution_notes: str) -> bool:
    subject = f"Complaint Resolved - {complaint_number}"
    body_html = get_complaint_resolved_email_template(
        customer_name, complaint_number, complaint_title, resolution_notes
    )
    
    return send_email(
        to_email=customer_email,
        subject=subject,
        body_html=body_html
    )



def get_password_reset_otp_email_template(customer_name: str, otp_code: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Password Reset OTP</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#111;">Password Reset Request</h2>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:16px; color:#111; margin:0 0 10px;">Hi {customer_name},</p>
<p style="font-size:15px; color:#444; line-height:24px;">We received a request to reset your password. Use the OTP code below to reset your password:</p>
</td>
</tr>

<tr>
<td align="center" style="padding:20px 40px;">
<div style="background:#f8f9fb; border-radius:8px; padding:30px; border:2px dashed #00968f;">
<p style="margin:0 0 10px; font-size:14px; color:#666; text-transform:uppercase; letter-spacing:1px;">Your OTP Code</p>
<p style="margin:0; font-size:36px; color:#000; font-weight:700; letter-spacing:8px;">{otp_code}</p>
</div>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="font-size:14px; color:#444; line-height:24px;">This OTP code will expire in <strong>10 minutes</strong>.</p>
<p style="font-size:14px; color:#444; line-height:24px; margin-top:15px;">If you didn't request a password reset, please ignore this email or contact our support team if you have concerns.</p>
</td>
</tr>

<tr>
<td style="padding:10px 40px;">
<div style="background:#fff3cd; border-left:4px solid #ffc107; padding:15px; border-radius:4px;">
<p style="margin:0; font-size:13px; color:#856404; line-height:20px;">⚠️ <strong>Security Notice:</strong> Never share your OTP code with anyone. ARVO staff will never ask for your OTP.</p>
</div>
</td>
</tr>

<tr>
<td align="center" style="padding:30px 40px;">
<p style="font-size:13px; color:#777;">Need help? Contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#000; font-weight:600; text-decoration:none;">support@arvomobile.co.uk</a></p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_password_reset_otp_email(customer_email: str, customer_name: str, otp_code: str) -> bool:
    subject = "Password Reset OTP - ARVO"
    body_html = get_password_reset_otp_email_template(customer_name, otp_code)
    
    return send_email(
        to_email=customer_email,
        subject=subject,
        body_html=body_html
    )


def get_child_login_otp_email_template(parent_name: str, child_name: str, mobile_number: str, otp_code: str) -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>Child Device Login OTP</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial,sans-serif;">

<table width="100%" bgcolor="#f4f6f8" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:20px;">

<table width="600" bgcolor="#ffffff" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

<tr>
<td align="center" style="padding:40px 30px 20px;">
<img src="https://arvomobile.co.uk/ARVO_LOGO.png" width="200" alt="ARVO Logo" style="display:block;">
</td>
</tr>

<tr>
<td align="center" style="padding:10px 40px;">
<h2 style="margin:0; font-size:24px; font-weight:600; color:#111;">Child Device Login Request</h2>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="margin:0 0 15px; font-size:16px; line-height:24px; color:#333;">
Dear {parent_name},
</p>
<p style="margin:0 0 15px; font-size:16px; line-height:24px; color:#333;">
A login request has been made for <strong>{child_name}'s</strong> device with mobile number <strong>{mobile_number}</strong>.
</p>
<p style="margin:0 0 15px; font-size:16px; line-height:24px; color:#333;">
Please use the following One-Time Password (OTP) to complete the login:
</p>
</td>
</tr>

<tr>
<td align="center" style="padding:20px 40px;">
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding:20px; border-radius:12px; display:inline-block;">
<p style="margin:0; font-size:36px; font-weight:700; color:#ffffff; letter-spacing:8px; font-family:monospace;">
{otp_code}
</p>
</div>
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="margin:0 0 15px; font-size:14px; line-height:22px; color:#666;">
This OTP is valid for <strong>10 minutes</strong> only.
</p>
<p style="margin:0 0 15px; font-size:14px; line-height:22px; color:#666;">
If you did not request this login, please ignore this email or contact our support team immediately.
</p>
</td>
</tr>

<tr>
<td style="padding:30px 40px 20px;">
<hr style="border:none; border-top:1px solid #e0e0e0; margin:0;">
</td>
</tr>

<tr>
<td style="padding:20px 40px;">
<p style="margin:0 0 10px; font-size:14px; color:#999;">
Best regards,<br>
<strong style="color:#667eea;">ARVO Mobile Team</strong>
</p>
</td>
</tr>

<tr>
<td align="center" style="padding:20px 40px 40px;">
<p style="margin:0; font-size:12px; color:#999; line-height:18px;">
This is an automated message. Please do not reply to this email.<br>
For support, contact us at <a href="mailto:support@arvomobile.co.uk" style="color:#667eea; text-decoration:none;">support@arvomobile.co.uk</a>
</p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>"""


def send_child_login_otp_email(parent_email: str, parent_name: str, child_name: str, mobile_number: str, otp_code: str) -> bool:
    subject = "Child Device Login OTP - ARVO"
    body_html = get_child_login_otp_email_template(parent_name, child_name, mobile_number, otp_code)
    
    return send_email(
        to_email=parent_email,
        subject=subject,
        body_html=body_html
    )
