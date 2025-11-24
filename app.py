from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, timedelta, time
import calendar
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import json
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import string
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Email configuration (Gmail SMTP)
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'epicedgecreative@gmail.com'
SMTP_PASS = 'lgte eojw nwsp fqlp'  # Provided app password
EMAIL_FROM = SMTP_USER
USE_TLS = True

# Base URL for email links - Your website URL
BASE_URL = 'https://cosyhideawaykenya.amutsa.com'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'Real estate',
    'user': 'root',
    'password': '',
    'port': 3306
}

def get_db_connection():
    """Create and return database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_booking_confirmation_email(customer_email, customer_name, property_title, property_city, start_date, end_date, booking_type, booking_id):
    """Send booking confirmation email to customer"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = customer_email
        # Set appropriate subject based on booking type
        if booking_type == 'sale':
            msg['Subject'] = f'Viewing Request Confirmation - {property_title}'
        elif booking_type == 'rent':
            msg['Subject'] = f'Rental Booking Request Confirmation - {property_title}'
        else:
            msg['Subject'] = f'Booking Confirmation - {property_title}'
        
        # Format dates with correct terminology based on booking type
        date_info = ""
        if start_date:
            start_str = datetime.strptime(str(start_date), '%Y-%m-%d').strftime('%B %d, %Y')
            if booking_type == 'airbnb':
                date_info = f"<p><strong>Check-in Date:</strong> {start_str}</p>"
                if end_date:
                    end_str = datetime.strptime(str(end_date), '%Y-%m-%d').strftime('%B %d, %Y')
                    date_info += f"<p><strong>Check-out Date:</strong> {end_str}</p>"
            elif booking_type == 'rent':
                date_info = f"<p><strong>Preferred Booking Date:</strong> {start_str}</p>"
            elif booking_type == 'sale':
                date_info = f"<p><strong>Preferred Viewing Date:</strong> {start_str}</p>"
        
        # Determine email content based on booking type
        if booking_type == 'sale':
            email_title = "Viewing Request Confirmation"
            email_intro = "Thank you for your viewing request! We have received your request and will contact you shortly to schedule a viewing."
            details_title = "Viewing Details"
            closing_text = "Our team will review your viewing request and contact you soon to schedule a convenient time."
        elif booking_type == 'rent':
            email_title = "Rental Booking Request Confirmation"
            email_intro = "Thank you for your rental booking request! We have received your request and will process it shortly."
            details_title = "Booking Details"
            closing_text = "Our team will review your booking request and contact you soon to confirm the details."
        else:
            email_title = "Booking Confirmation"
            email_intro = "Thank you for your booking request! We have received your booking and will process it shortly."
            details_title = "Booking Details"
            closing_text = "Our team will review your booking and contact you soon to confirm the details."
        
        # Email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">{email_title}</h2>
                <p>Dear {customer_name},</p>
                <p>{email_intro}</p>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">{details_title}</h3>
                    <p><strong>Property:</strong> {property_title}</p>
                    <p><strong>Location:</strong> {property_city}</p>
                    <p><strong>Type:</strong> {booking_type.upper()}</p>
                    {date_info}
                </div>
                
                <p>{closing_text}</p>
                <p>If you have any questions, please don't hesitate to contact us.</p>
                
                <p style="margin-top: 30px;">
                    Best regards,<br>
                    <strong>Cosy Hideaway kenya</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Confirmation email sent to {customer_email}")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

def send_admin_booking_notification(booking_id, property_title, property_city, customer_name, customer_email, customer_phone, booking_type, start_date, end_date, message):
    """Send email notification to admin when a new booking is received"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_FROM  # Send to admin email (your email)
        msg['Subject'] = f'New Booking Received - #{booking_id} - {property_title}'
        
        # Format dates with correct terminology based on booking type
        date_info = ""
        if start_date:
            start_str = datetime.strptime(str(start_date), '%Y-%m-%d').strftime('%B %d, %Y')
            if booking_type == 'airbnb':
                date_info = f"<p><strong>Check-in Date:</strong> {start_str}</p>"
                if end_date:
                    end_str = datetime.strptime(str(end_date), '%Y-%m-%d').strftime('%B %d, %Y')
                    date_info += f"<p><strong>Check-out Date:</strong> {end_str}</p>"
            elif booking_type == 'rent':
                date_info = f"<p><strong>Preferred Booking Date:</strong> {start_str}</p>"
            elif booking_type == 'sale':
                date_info = f"<p><strong>Preferred Viewing Date:</strong> {start_str}</p>"
        
        # Customer contact info
        contact_info = f"<p><strong>Name:</strong> {customer_name}</p>"
        contact_info += f"<p><strong>Email:</strong> {customer_email}</p>"
        if customer_phone:
            contact_info += f"<p><strong>Phone:</strong> {customer_phone}</p>"
        
        # Email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #dc2626;">New Booking Received</h2>
                <p>A new booking has been submitted and requires your attention.</p>
                
                <div style="background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #dc2626;">Booking Information</h3>
                    <p><strong>Booking ID:</strong> #{booking_id}</p>
                    <p><strong>Property:</strong> {property_title}</p>
                    <p><strong>Location:</strong> {property_city}</p>
                    <p><strong>Type:</strong> {booking_type.upper()}</p>
                    {date_info}
                </div>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Customer Contact Information</h3>
                    {contact_info}
                </div>
                
                {f'<div style="background-color: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0;"><p><strong>Message from customer:</strong></p><p>{message}</p></div>' if message else ''}
                
                <div style="background-color: #dbeafe; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Action Required:</strong> Please review this booking in the admin panel and contact the customer to confirm.</p>
                </div>
                
                <p style="margin-top: 30px;">
                    This is an automated notification from<br>
                    <strong>Cosy Hideaway kenya</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Admin notification email sent for booking #{booking_id}")
    except Exception as e:
        print(f"Error sending admin notification email: {e}")
        raise

def send_welcome_email(user_email, user_name):
    """Send welcome email to newly registered users"""
    try:
        # Default to tenant dashboard for new registrations
        dashboard_url = f"{BASE_URL}/tenant/dashboard"
        login_url = f"{BASE_URL}/login?next={dashboard_url}"
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = user_email
        msg['Subject'] = 'Welcome to Cosy Hideaway kenya!'
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Welcome to Cosy Hideaway kenya!</h1>
                </div>
                
                <div style="background-color: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p>Dear {user_name},</p>
                    
                    <p>Thank you for joining <strong>Cosy Hideaway kenya</strong>! We're excited to have you as part of our community.</p>
                    
                    <div style="background-color: #f0f9ff; border-left: 4px solid #2563eb; padding: 20px; margin: 20px 0; border-radius: 5px;">
                        <h3 style="margin-top: 0; color: #2563eb;">What you can do now:</h3>
                        <ul style="margin: 10px 0; padding-left: 20px; color: #1f2937;">
                            <li>Browse our extensive collection of properties for sale, rent, and AirBnB</li>
                            <li>Save your favorite properties to view later</li>
                            <li>Book property viewings and rentals</li>
                            <li>Manage your bookings and rental payments</li>
                            <li>Submit maintenance requests</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{login_url}" style="display: inline-block; background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; transition: transform 0.2s;">Login to Your Dashboard</a>
                    </div>
                    
                    <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #1f2937;">Need Help?</h4>
                        <p style="margin: 5px 0; color: #6b7280;">If you have any questions or need assistance, feel free to:</p>
                        <ul style="margin: 10px 0; padding-left: 20px; color: #6b7280;">
                            <li>Visit our <a href="{base_url}/contact" style="color: #2563eb; text-decoration: none;">Contact Us</a> page</li>
                            <li>Email us at <a href="mailto:epicedgecreative@gmail.com" style="color: #2563eb; text-decoration: none;">epicedgecreative@gmail.com</a></li>
                            <li>Call us at <a href="tel:+254787205456" style="color: #2563eb; text-decoration: none;">+254 78 720 5456</a></li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 30px; color: #6b7280; font-size: 14px;">
                        We're here to help you find your perfect home. Happy house hunting!
                    </p>
                    
                    <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                        Best regards,<br>
                        <strong>The Cosy Hideaway kenya Team</strong>
                    </p>
                </div>
                
                <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
                    <p style="margin: 5px 0;">© 2025 Cosy Hideaway kenya. All rights reserved.</p>
                    <p style="margin: 5px 0;">
                        <a href="{base_url}/terms" style="color: #9ca3af; text-decoration: none;">Terms of Service</a> | 
                        <a href="{base_url}/privacy" style="color: #9ca3af; text-decoration: none;">Privacy Policy</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Welcome email sent to {user_email}")
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        raise

def send_booking_confirmed_email(customer_email, customer_name, property_title, property_city, booking_type, start_date, end_date):
    """Send email to customer when their booking is confirmed by admin"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = customer_email
        
        # Get viewing hours based on day of week (for rent/sale bookings)
        viewing_hours_closing = ""
        if start_date and booking_type in ['rent', 'sale']:
            start_date_obj = datetime.strptime(str(start_date), '%Y-%m-%d').date()
            day_name = start_date_obj.strftime('%A')
            if day_name == 'Sunday':
                viewing_hours_closing = "Please note: We are closed on Sundays. Please contact us to reschedule for another day."
            elif day_name == 'Saturday':
                viewing_hours_closing = "Please visit us during our business hours (9:30 AM - 1:00 PM) on the scheduled date."
            else:  # Monday to Friday
                viewing_hours_closing = "Please visit us during our business hours (9:00 AM - 5:00 PM) on the scheduled date."
        
        # Set appropriate subject and content based on booking type
        if booking_type == 'sale':
            msg['Subject'] = f'Viewing Confirmed - {property_title}'
            email_title = "Viewing Confirmed!"
            email_intro = "Great news! Your property viewing request has been confirmed."
            details_title = "Confirmed Viewing Details"
            closing_text = f"Your viewing is now confirmed. {viewing_hours_closing} We look forward to showing you the property!"
        elif booking_type == 'rent':
            msg['Subject'] = f'Viewing Confirmed - {property_title}'
            email_title = "Viewing Confirmed!"
            email_intro = "Great news! Your rental property viewing request has been confirmed."
            details_title = "Confirmed Viewing Details"
            closing_text = f"Your viewing is now confirmed. {viewing_hours_closing} We look forward to showing you the property!"
        else:
            msg['Subject'] = f'Booking Confirmed - {property_title}'
            email_title = "Booking Confirmed!"
            email_intro = "Great news! Your booking has been confirmed."
            details_title = "Confirmed Booking Details"
            closing_text = "Your booking is now confirmed and ready. We look forward to hosting you!"
        
        # Format dates with correct terminology based on booking type
        date_info = ""
        viewing_hours_text = ""
        if start_date:
            start_date_obj = datetime.strptime(str(start_date), '%Y-%m-%d').date()
            start_str = start_date_obj.strftime('%B %d, %Y')
            day_name = start_date_obj.strftime('%A')  # Get day name (Monday, Tuesday, etc.)
            
            if booking_type == 'airbnb':
                date_info = f"<p><strong>Check-in Date:</strong> {start_str}</p>"
                if end_date:
                    end_str = datetime.strptime(str(end_date), '%Y-%m-%d').strftime('%B %d, %Y')
                    date_info += f"<p><strong>Check-out Date:</strong> {end_str}</p>"
            elif booking_type in ['rent', 'sale']:
                date_info = f"<p><strong>Viewing Date:</strong> {start_str} ({day_name})</p>"
                # Determine viewing hours based on day of week
                if day_name == 'Sunday':
                    viewing_hours_text = "Closed (We don't work on Sundays)"
                    date_info += f"<p><strong>Viewing Hours:</strong> <span style='color: #dc2626;'>{viewing_hours_text}</span></p>"
                    date_info += f"<p style='color: #dc2626; font-size: 0.9em;'><em>Please note: We are closed on Sundays. Please contact us to reschedule for another day.</em></p>"
                elif day_name == 'Saturday':
                    viewing_hours_text = "9:30 AM - 1:00 PM"
                    date_info += f"<p><strong>Viewing Hours:</strong> {viewing_hours_text}</p>"
                else:  # Monday to Friday
                    viewing_hours_text = "9:00 AM - 5:00 PM"
                    date_info += f"<p><strong>Viewing Hours:</strong> {viewing_hours_text}</p>"
        
        # Email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #10b981;">{email_title}</h2>
                <p>Dear {customer_name},</p>
                <p>{email_intro}</p>
                
                <div style="background-color: #d1fae5; border-left: 4px solid #10b981; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #10b981;">{details_title}</h3>
                    <p><strong>Property:</strong> {property_title}</p>
                    <p><strong>Location:</strong> {property_city}</p>
                    <p><strong>Type:</strong> {booking_type.upper()}</p>
                    {date_info}
                </div>
                
                <p>{closing_text}</p>
                <p>If you have any questions or need to make changes, please contact us.</p>
                
                <p style="margin-top: 30px;">
                    Best regards,<br>
                    <strong>Cosy Hideaway kenya</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Booking confirmation email sent to {customer_email}")
    except Exception as e:
        print(f"Error sending booking confirmation email: {e}")
        raise

def generate_random_password(length=12):
    """Generate a random secure password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def send_account_creation_email(user_email, username, password, full_name, role='user'):
    """Send account creation email with login credentials"""
    try:
        # Determine dashboard URL based on role
        if role == 'admin':
            dashboard_url = f"{BASE_URL}/admin/dashboard"
        elif role == 'manager':
            dashboard_url = f"{BASE_URL}/manager/dashboard"
        else:
            dashboard_url = f"{BASE_URL}/tenant/dashboard"
        
        login_url = f"{BASE_URL}/login?next={dashboard_url}"
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = user_email
        msg['Subject'] = 'Your Account Has Been Created - Cosy Hideaway kenya'
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #3b82f6;">Welcome to Cosy Hideaway kenya!</h2>
                <p>Dear {full_name or username},</p>
                <p>Your account has been created by an administrator. You can now access the platform using the credentials below:</p>
                
                <div style="background-color: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #3b82f6;">Your Login Credentials</h3>
                    <p style="margin: 5px 0;"><strong>Username:</strong> {username}</p>
                    <p style="margin: 5px 0;"><strong>Email:</strong> {user_email}</p>
                    <p style="margin: 5px 0;"><strong>Temporary Password:</strong> <code style="background-color: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-family: monospace;">{password}</code></p>
                </div>
                
                <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #f59e0b;">Important Security Notice</h3>
                    <p style="margin: 5px 0;">For your security, please change your password after your first login.</p>
                    <p style="margin: 5px 0;">You can change your password from your dashboard settings.</p>
                </div>
                
                <p style="margin-top: 20px;">
                    <a href="{login_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Login to Your Dashboard</a>
                </p>
                
                <p style="margin-top: 30px; color: #6b7280; font-size: 12px;">
                    If you did not expect this email, please contact our support team immediately.
                </p>
                
                <p style="margin-top: 30px;">
                    Best regards,<br>
                    <strong>Cosy Hideaway kenya Team</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Account creation email sent to {user_email}")
        return True
    except Exception as e:
        print(f"Error sending account creation email to {user_email}: {e}")
        return False

def send_reminder_email(recipient_email, recipient_name, reminder_type, subject, message, details_html):
    """Send reminder email to recipient"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #3b82f6;">Reminder: {subject}</h2>
                <p>Dear {recipient_name},</p>
                <p>{message}</p>
                {details_html}
                <p style="margin-top: 30px;">
                    Best regards,<br>
                    <strong>Cosy Hideaway kenya</strong>
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Reminder email sent to {recipient_email}: {subject}")
        return True
    except Exception as e:
        print(f"Error sending reminder email to {recipient_email}: {e}")
        return False

def check_and_send_reminders():
    """Check for upcoming events and send reminders"""
    conn = get_db_connection()
    if not conn:
        print("Database connection error in reminder checker")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Check for check-in reminders (1 day before)
        cursor.execute("""
            SELECT b.id, b.start_date, 
                   COALESCE(u.email, b.guest_email) as email,
                   COALESCE(u.full_name, b.guest_name, 'Guest') as name,
                   p.title as property_title, p.city as property_city
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.status = 'confirmed'
            AND b.start_date = %s
            AND b.start_date IS NOT NULL
        """, (tomorrow,))
        
        check_in_bookings = cursor.fetchall()
        for booking in check_in_bookings:
            # Check if reminder already sent
            cursor.execute("""
                SELECT id FROM reminders_sent 
                WHERE reminder_type = 'check_in' 
                AND reference_id = %s 
                AND reference_type = 'booking'
                AND reminder_date = %s
            """, (booking['id'], booking['start_date']))
            
            if not cursor.fetchone():
                details = f"""
                <div style="background-color: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #3b82f6;">Check-in Details</h3>
                    <p><strong>Property:</strong> {booking['property_title']}</p>
                    <p><strong>Location:</strong> {booking['property_city']}</p>
                    <p><strong>Check-in Date:</strong> {booking['start_date'].strftime('%B %d, %Y')}</p>
                </div>
                """
                
                if send_reminder_email(
                    booking['email'],
                    booking['name'],
                    'check_in',
                    f"Check-in Reminder - {booking['property_title']}",
                    "This is a friendly reminder that your check-in is scheduled for tomorrow.",
                    details
                ):
                    # Record reminder sent
                    cursor.execute("""
                        INSERT INTO reminders_sent (reminder_type, reference_id, reference_type, reminder_date, recipient_email, recipient_name)
                        VALUES ('check_in', %s, 'booking', %s, %s, %s)
                    """, (booking['id'], booking['start_date'], booking['email'], booking['name']))
        
        # Check for check-out reminders (1 day before)
        cursor.execute("""
            SELECT b.id, b.end_date,
                   COALESCE(u.email, b.guest_email) as email,
                   COALESCE(u.full_name, b.guest_name, 'Guest') as name,
                   p.title as property_title, p.city as property_city
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.status = 'confirmed'
            AND b.end_date = %s
            AND b.end_date IS NOT NULL
        """, (tomorrow,))
        
        check_out_bookings = cursor.fetchall()
        for booking in check_out_bookings:
            cursor.execute("""
                SELECT id FROM reminders_sent 
                WHERE reminder_type = 'check_out' 
                AND reference_id = %s 
                AND reference_type = 'booking'
                AND reminder_date = %s
            """, (booking['id'], booking['end_date']))
            
            if not cursor.fetchone():
                details = f"""
                <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #f59e0b;">Check-out Details</h3>
                    <p><strong>Property:</strong> {booking['property_title']}</p>
                    <p><strong>Location:</strong> {booking['property_city']}</p>
                    <p><strong>Check-out Date:</strong> {booking['end_date'].strftime('%B %d, %Y')}</p>
                </div>
                """
                
                if send_reminder_email(
                    booking['email'],
                    booking['name'],
                    'check_out',
                    f"Check-out Reminder - {booking['property_title']}",
                    "This is a friendly reminder that your check-out is scheduled for tomorrow.",
                    details
                ):
                    cursor.execute("""
                        INSERT INTO reminders_sent (reminder_type, reference_id, reference_type, reminder_date, recipient_email, recipient_name)
                        VALUES ('check_out', %s, 'booking', %s, %s, %s)
                    """, (booking['id'], booking['end_date'], booking['email'], booking['name']))
        
        # Check for payment due reminders (1 day before)
        cursor.execute("""
            SELECT r.id, r.next_due_date, r.rent_amount,
                   u.email, u.full_name as name,
                   p.title as property_title
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.status = 'active'
            AND r.next_due_date = %s
            AND r.next_due_date IS NOT NULL
        """, (tomorrow,))
        
        payment_due_rentals = cursor.fetchall()
        for rental in payment_due_rentals:
            cursor.execute("""
                SELECT id FROM reminders_sent 
                WHERE reminder_type = 'payment_due' 
                AND reference_id = %s 
                AND reference_type = 'rental'
                AND reminder_date = %s
            """, (rental['id'], rental['next_due_date']))
            
            if not cursor.fetchone():
                details = f"""
                <div style="background-color: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #ef4444;">Payment Due Details</h3>
                    <p><strong>Property:</strong> {rental['property_title']}</p>
                    <p><strong>Amount Due:</strong> KSH {rental['rent_amount']:,.2f}</p>
                    <p><strong>Due Date:</strong> {rental['next_due_date'].strftime('%B %d, %Y')}</p>
                </div>
                """
                
                if send_reminder_email(
                    rental['email'],
                    rental['name'],
                    'payment_due',
                    f"Payment Due Reminder - {rental['property_title']}",
                    "This is a friendly reminder that your rent payment is due tomorrow.",
                    details
                ):
                    cursor.execute("""
                        INSERT INTO reminders_sent (reminder_type, reference_id, reference_type, reminder_date, recipient_email, recipient_name)
                        VALUES ('payment_due', %s, 'rental', %s, %s, %s)
                    """, (rental['id'], rental['next_due_date'], rental['email'], rental['name']))
        
        # Check for lease expiration reminders (30 days, 7 days, 1 day before)
        expiration_dates = [today + timedelta(days=30), today + timedelta(days=7), tomorrow]
        for exp_date in expiration_dates:
            cursor.execute("""
                SELECT r.id, r.lease_end,
                       u.email, u.full_name as name,
                       p.title as property_title
                FROM rentals r
                JOIN properties p ON r.property_id = p.id
                JOIN users u ON r.tenant_id = u.id
                WHERE r.status = 'active'
                AND r.lease_end = %s
                AND r.lease_end IS NOT NULL
            """, (exp_date,))
            
            expiring_rentals = cursor.fetchall()
            for rental in expiring_rentals:
                days_left = (rental['lease_end'] - today).days
                cursor.execute("""
                    SELECT id FROM reminders_sent 
                    WHERE reminder_type = 'lease_expiration' 
                    AND reference_id = %s 
                    AND reference_type = 'rental'
                    AND reminder_date = %s
                """, (rental['id'], rental['lease_end']))
                
                if not cursor.fetchone():
                    if days_left == 30:
                        message = "This is a reminder that your lease will expire in 30 days."
                    elif days_left == 7:
                        message = "This is a reminder that your lease will expire in 7 days."
                    else:
                        message = "This is a reminder that your lease expires tomorrow."
                    
                    details = f"""
                    <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #f59e0b;">Lease Expiration Details</h3>
                        <p><strong>Property:</strong> {rental['property_title']}</p>
                        <p><strong>Lease End Date:</strong> {rental['lease_end'].strftime('%B %d, %Y')}</p>
                        <p><strong>Days Remaining:</strong> {days_left} day{'s' if days_left != 1 else ''}</p>
                    </div>
                    """
                    
                    if send_reminder_email(
                        rental['email'],
                        rental['name'],
                        'lease_expiration',
                        f"Lease Expiration Reminder - {rental['property_title']}",
                        message,
                        details
                    ):
                        cursor.execute("""
                            INSERT INTO reminders_sent (reminder_type, reference_id, reference_type, reminder_date, recipient_email, recipient_name)
                            VALUES ('lease_expiration', %s, 'rental', %s, %s, %s)
                        """, (rental['id'], rental['lease_end'], rental['email'], rental['name']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Error as e:
        print(f"Error in reminder checker: {e}")
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass

def add_cycle(date_obj, cycle):
    """Return next due date based on payment cycle"""
    if not date_obj:
        return None
    if cycle == 'monthly':
        months = 1
    elif cycle == 'quarterly':
        months = 3
    elif cycle == 'yearly':
        months = 12
    else:
        months = 1
    month = date_obj.month - 1 + months
    year = date_obj.year + month // 12
    month = month % 12 + 1
    day = min(date_obj.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    """Decorator to require manager or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        if session.get('role') not in ['manager', 'admin']:
            flash('Access denied. Manager privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Home page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('index.html', properties=[], user=session.get('user'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Get featured properties, or fallback to recent active properties if no featured ones
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY COALESCE(p.featured, 0) DESC, p.created_at DESC
            LIMIT 6
        """)
        properties = cursor.fetchall()
        
        # Process images
        for prop in properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')
            else:
                prop['images'] = []
        
        cursor.close()
        conn.close()
        
        user = None
        if 'user_id' in session:
            user = {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role')
            }
        
        return render_template('index.html', properties=properties, user=user)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading properties', 'error')
        return render_template('index.html', properties=[], user=session.get('user'))

@app.route('/properties')
def properties():
    """List all properties with advanced filters"""
    property_type = request.args.get('type', 'all')
    search = request.args.get('search', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    city = request.args.get('city', '')
    bedrooms = request.args.get('bedrooms', '')
    bathrooms = request.args.get('bathrooms', '')
    amenities = request.args.get('amenities', '')
    sort_by = request.args.get('sort', 'newest')  # newest, price_low, price_high, featured
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 8
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('properties.html', properties=[], filters={}, pagination=None)
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Build query
        query = """
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE p.status = 'active'
        """
        params = []
        
        if property_type != 'all':
            query += " AND p.property_type = %s"
            params.append(property_type)
        
        if search:
            query += " AND (p.title LIKE %s OR p.description LIKE %s OR p.city LIKE %s OR p.state LIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        if min_price:
            query += " AND p.price >= %s"
            params.append(float(min_price))
        
        if max_price:
            query += " AND p.price <= %s"
            params.append(float(max_price))
        
        if city:
            query += " AND p.city LIKE %s"
            params.append(f"%{city}%")
        
        if bedrooms:
            query += " AND p.bedrooms >= %s"
            params.append(int(bedrooms))
        
        if bathrooms:
            query += " AND p.bathrooms >= %s"
            params.append(float(bathrooms))
        
        if amenities:
            # Search for amenities in the amenities field
            amenity_list = amenities.split(',')
            amenity_conditions = []
            for amenity in amenity_list:
                amenity = amenity.strip()
                if amenity:
                    amenity_conditions.append("p.amenities LIKE %s")
                    params.append(f"%{amenity}%")
            if amenity_conditions:
                query += " AND (" + " OR ".join(amenity_conditions) + ")"
        
        # Build WHERE clause for count query (without JOIN and GROUP BY)
        where_clause = "WHERE p.status = 'active'"
        count_params = []
        
        if property_type != 'all':
            where_clause += " AND p.property_type = %s"
            count_params.append(property_type)
        
        if search:
            where_clause += " AND (p.title LIKE %s OR p.description LIKE %s OR p.city LIKE %s OR p.state LIKE %s)"
            search_term = f"%{search}%"
            count_params.extend([search_term, search_term, search_term, search_term])
        
        if min_price:
            where_clause += " AND p.price >= %s"
            count_params.append(float(min_price))
        
        if max_price:
            where_clause += " AND p.price <= %s"
            count_params.append(float(max_price))
        
        if city:
            where_clause += " AND p.city LIKE %s"
            count_params.append(f"%{city}%")
        
        if bedrooms:
            where_clause += " AND p.bedrooms >= %s"
            count_params.append(int(bedrooms))
        
        if bathrooms:
            where_clause += " AND p.bathrooms >= %s"
            count_params.append(float(bathrooms))
        
        if amenities:
            amenity_list = amenities.split(',')
            amenity_conditions = []
            for amenity in amenity_list:
                amenity = amenity.strip()
                if amenity:
                    amenity_conditions.append("p.amenities LIKE %s")
                    count_params.append(f"%{amenity}%")
            if amenity_conditions:
                where_clause += " AND (" + " OR ".join(amenity_conditions) + ")"
        
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) as total FROM properties p {where_clause}"
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['total']
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1  # Ceiling division
        
        query += " GROUP BY p.id"
        
        # Add sorting
        if sort_by == 'price_low':
            query += " ORDER BY p.price ASC"
        elif sort_by == 'price_high':
            query += " ORDER BY p.price DESC"
        elif sort_by == 'featured':
            query += " ORDER BY p.featured DESC, p.created_at DESC"
        else:  # newest
            query += " ORDER BY p.created_at DESC"
        
        # Add pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        properties = cursor.fetchall()
        
        # Get unique cities for filter dropdown
        cursor.execute("SELECT DISTINCT city FROM properties WHERE status = 'active' AND city IS NOT NULL ORDER BY city")
        cities = [row['city'] for row in cursor.fetchall()]
        
        # Process images
        for prop in properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')
            else:
                prop['images'] = []
        
        cursor.close()
        conn.close()
        
        filters = {
            'type': property_type,
            'search': search,
            'min_price': min_price,
            'max_price': max_price,
            'city': city,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'amenities': amenities,
            'sort': sort_by,
            'cities': cities
        }
        
        user = None
        if 'user_id' in session:
            user = {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role')
            }
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None
        }
        
        return render_template('properties.html', properties=properties, filters=filters, user=user, pagination=pagination)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading properties', 'error')
        user = None
        if 'user_id' in session:
            user = {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role')
            }
        return render_template('properties.html', properties=[], filters={}, user=user, pagination=None)

@app.route('/property/<int:property_id>')
def property_detail(property_id):
    """Property detail page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('properties'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property details
        cursor.execute("""
            SELECT * FROM properties WHERE id = %s AND status = 'active'
        """, (property_id,))
        property = cursor.fetchone()
        
        if not property:
            flash('Property not found', 'error')
            return redirect(url_for('properties'))
        
        # Get property images
        cursor.execute("""
            SELECT image_path FROM property_images WHERE property_id = %s ORDER BY id
        """, (property_id,))
        images = [row['image_path'] for row in cursor.fetchall()]
        property['images'] = images
        
        # Get similar properties
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE p.property_type = %s 
            AND p.id != %s 
            AND p.status = 'active'
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT 4
        """, (property['property_type'], property_id))
        similar = cursor.fetchall()
        
        for prop in similar:
            if prop['images']:
                prop['images'] = prop['images'].split(',')[:1]
            else:
                prop['images'] = []
        
        cursor.close()
        conn.close()
        
        user = None
        if 'user_id' in session:
            user = {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role')
            }
        
        return render_template('property_detail.html', property=property, similar_properties=similar, user=user)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading property', 'error')
        return redirect(url_for('properties'))

@app.route('/about')
def about():
    """About page"""
    user = None
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
    return render_template('about.html', user=user)

@app.route('/terms')
def terms():
    """Terms of Service page"""
    user = None
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
    return render_template('terms.html', user=user)

@app.route('/privacy')
def privacy():
    """Privacy Policy page"""
    user = None
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
    return render_template('privacy.html', user=user)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        if not name or not email or not message:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('contact'))
        
        try:
            # Send email to admin
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM
            msg['To'] = EMAIL_FROM  # Send to admin
            msg['Subject'] = f'Contact Form: {subject or "No Subject"}'
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2563eb;">New Contact Form Submission</h2>
                    <p><strong>Name:</strong> {name}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Subject:</strong> {subject or 'No Subject'}</p>
                    <p><strong>Message:</strong></p>
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        {message}
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            if USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            
            flash('Thank you for contacting us! We will get back to you soon.', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            print(f"Error sending contact email: {e}")
            flash('Error sending message. Please try again later.', 'error')
            return redirect(url_for('contact'))
    
    user = None
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
    return render_template('contact.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('register'))
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('register'))
            
            # Hash password and insert user
            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role)
                VALUES (%s, %s, %s, %s, 'user')
            """, (username, email, password_hash, full_name))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Send welcome email
            try:
                send_welcome_email(email, full_name or username)
            except Exception as e:
                print(f"Error sending welcome email: {e}")
                # Don't fail registration if email fails
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Error as e:
            conn.rollback()
            print(f"Error: {e}")
            flash('Error during registration', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter username and password', 'error')
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('login'))
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                # Check if user is suspended or deleted
                if user.get('status') == 'suspended':
                    flash('Your account has been suspended. Please contact an administrator.', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('login'))
                elif user.get('status') == 'deleted':
                    flash('Your account has been deleted. Please contact an administrator.', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('login'))
                # Set session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['full_name'] = user.get('full_name', '')
                
                cursor.close()
                conn.close()
                
                # Check if there's a next parameter (redirect after login)
                next_url = request.args.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Redirect based on role
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user['role'] == 'manager':
                    return redirect(url_for('manager_dashboard'))
                else:
                    return redirect(url_for('tenant_dashboard'))
            else:
                flash('Invalid username or password', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
                
        except Error as e:
            print(f"Error: {e}")
            flash('Error during login', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard"""
    if session.get('role') != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_dashboard.html', user=session.get('user'), stats={})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) as total FROM properties")
        total_properties = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE status = 'active'")
        active_properties = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings")
        total_bookings = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE status = 'pending'")
        pending_bookings = cursor.fetchone()['total']
        
        # Get rental statistics
        cursor.execute("SELECT COUNT(*) as total FROM rentals WHERE status = 'active'")
        active_rentals = cursor.fetchone()['total']
        
        # Get reports statistics
        cursor.execute("SELECT COUNT(*) as total FROM rental_reports WHERE status IN ('open', 'in_progress')")
        open_reports = cursor.fetchone()['total']
        
        # Get pending vacate notices count
        cursor.execute("SELECT COUNT(*) as total FROM rental_reports WHERE report_type = 'vacate' AND status IN ('open', 'in_progress')")
        pending_vacate_notices = cursor.fetchone()['total']
        
        # Get property type breakdown
        cursor.execute("SELECT property_type, COUNT(*) as count FROM properties WHERE status = 'active' GROUP BY property_type")
        property_types = cursor.fetchall()
        property_type_breakdown = {pt['property_type']: pt['count'] for pt in property_types}
        
        # Get revenue statistics (from rental payments and booking payments)
        cursor.execute("SELECT SUM(amount) as total FROM rental_payments WHERE payment_date IS NOT NULL")
        rental_revenue = cursor.fetchone()['total'] or 0
        
        # Get booking payments revenue (AirBnB confirmed bookings)
        cursor.execute("SELECT SUM(amount) as total FROM booking_payments WHERE payment_date IS NOT NULL")
        booking_revenue = cursor.fetchone()['total'] or 0
        
        total_revenue = (rental_revenue or 0) + (booking_revenue or 0)
        
        # Get recent bookings (including guest bookings)
        cursor.execute("""
            SELECT b.*, 
                   p.title as property_title, 
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   COALESCE(u.username, b.guest_email) as customer_username,
                   COALESCE(u.email, b.guest_email) as customer_email,
                   b.guest_phone
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            ORDER BY b.created_at DESC
            LIMIT 5
        """)
        recent_bookings = cursor.fetchall()
        
        # Get recent reports
        cursor.execute("""
            SELECT rr.*, p.title as property_title, u.full_name as tenant_name
            FROM rental_reports rr
            JOIN rentals r ON rr.rental_id = r.id
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON rr.reported_by = u.id
            ORDER BY rr.created_at DESC
            LIMIT 5
        """)
        recent_reports = cursor.fetchall()
        
        # Get upcoming lease expirations (within 30 days)
        today = date.today()
        lease_expiry_date = today + timedelta(days=30)
        cursor.execute("""
            SELECT r.*, p.title as property_title, u.full_name as tenant_name, u.email as tenant_email
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.status = 'active'
            AND r.lease_end IS NOT NULL
            AND r.lease_end <= %s
            AND r.lease_end >= %s
            ORDER BY r.lease_end ASC
            LIMIT 5
        """, (lease_expiry_date, today))
        expiring_leases = cursor.fetchall()
        
        # Get recent user registrations
        cursor.execute("""
            SELECT id, username, email, full_name, created_at, role
            FROM users
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_users = cursor.fetchall()
        
        # Get upcoming check-ins - Show all confirmed bookings with future start dates OR ongoing bookings
        # This shows bookings that need check-in preparation (AirBnB and Rent)
        cursor.execute("""
            SELECT b.*, p.title as property_title, p.property_type,
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   DATEDIFF(b.start_date, CURDATE()) as days_until,
                   b.booking_type as b_booking_type,
                   p.property_type as p_property_type
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.status = 'confirmed'
            AND b.start_date IS NOT NULL
            AND (
                b.start_date >= CURDATE()  -- Future check-ins
                OR (b.start_date < CURDATE() AND b.end_date >= CURDATE())  -- Ongoing bookings
            )
            ORDER BY b.start_date ASC
            LIMIT 20
        """)
        all_confirmed_future = cursor.fetchall()
        
        # Filter for AirBnB and Rent bookings
        upcoming_checkins = []
        for booking in all_confirmed_future:
            booking_type = booking.get('b_booking_type', '').lower() if booking.get('b_booking_type') else ''
            property_type = booking.get('p_property_type', '').lower() if booking.get('p_property_type') else ''
            
            if booking_type in ['airbnb', 'rent'] or property_type in ['airbnb', 'rent']:
                upcoming_checkins.append(booking)
        
        # Get monthly revenue (current month) - rental + booking payments
        cursor.execute("""
            SELECT SUM(amount) as total FROM rental_payments
            WHERE payment_date >= DATE_FORMAT(NOW(), '%Y-%m-01')
            AND payment_date IS NOT NULL
        """)
        monthly_rental_revenue = cursor.fetchone()['total'] or 0
        
        cursor.execute("""
            SELECT SUM(amount) as total FROM booking_payments
            WHERE payment_date >= DATE_FORMAT(NOW(), '%Y-%m-01')
            AND payment_date IS NOT NULL
        """)
        monthly_booking_revenue = cursor.fetchone()['total'] or 0
        
        monthly_revenue = (monthly_rental_revenue or 0) + (monthly_booking_revenue or 0)
        
        # Get recent properties
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT 10
        """)
        recent_properties = cursor.fetchall()
        
        for prop in recent_properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')[:1]
            else:
                prop['images'] = []
        
        stats = {
            'total_properties': total_properties,
            'active_properties': active_properties,
            'total_users': total_users,
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'active_rentals': active_rentals,
            'open_reports': open_reports,
            'pending_vacate_notices': pending_vacate_notices,
            'property_type_breakdown': property_type_breakdown,
            'total_revenue': float(total_revenue),
            'monthly_revenue': float(monthly_revenue)
        }
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_dashboard.html', 
                             user=user, 
                             stats=stats, 
                             recent_properties=recent_properties,
                             recent_bookings=recent_bookings,
                             recent_reports=recent_reports,
                             expiring_leases=expiring_leases,
                             recent_users=recent_users,
                             upcoming_checkins=upcoming_checkins)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('admin_dashboard.html', user=session.get('user'), stats={})

@app.route('/admin/properties')
@login_required
def admin_properties():
    """Admin properties management page"""
    if session.get('role') != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Admin',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('admin_properties.html', user=user, properties=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all properties with images
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        properties = cursor.fetchall()
        
        # Process images
        for prop in properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')
            else:
                prop['images'] = []
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_properties.html', user=user, properties=properties)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading properties', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Admin',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('admin_properties.html', user=user, properties=[])

@app.route('/manager/dashboard')
@manager_required
def manager_dashboard():
    """Manager dashboard with statistics"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_dashboard.html', user=user, stats={})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Statistics for manager dashboard
        stats = {}
        
        # Total and active properties
        cursor.execute("SELECT COUNT(*) as total FROM properties")
        stats['total_properties'] = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE status = 'active'")
        stats['active_properties'] = cursor.fetchone()['total'] or 0
        
        # Bookings statistics
        cursor.execute("SELECT COUNT(*) as total FROM bookings")
        stats['total_bookings'] = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE status = 'pending'")
        stats['pending_bookings'] = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE status = 'confirmed'")
        stats['confirmed_bookings'] = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE status = 'completed'")
        stats['completed_bookings'] = cursor.fetchone()['total'] or 0
        
        # Rentals statistics
        cursor.execute("SELECT COUNT(*) as total FROM rentals WHERE status = 'active'")
        stats['active_rentals'] = cursor.fetchone()['total'] or 0
        
        # Revenue (monthly) - current month
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM rental_payments
            WHERE payment_date >= DATE_FORMAT(NOW(), '%Y-%m-01')
            AND payment_date IS NOT NULL
        """)
        stats['monthly_revenue'] = float(cursor.fetchone()['total'] or 0)
        
        # Booking payments (AirBnB) monthly revenue
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM booking_payments
            WHERE payment_date >= DATE_FORMAT(NOW(), '%Y-%m-01')
            AND payment_date IS NOT NULL
        """)
        booking_revenue = float(cursor.fetchone()['total'] or 0)
        stats['monthly_revenue'] += booking_revenue
        
        # Maintenance requests
        cursor.execute("SELECT COUNT(*) as total FROM rental_reports WHERE report_type = 'maintenance' AND status IN ('open', 'in_progress')")
        stats['open_maintenance'] = cursor.fetchone()['total'] or 0
        
        # Vacate notices
        cursor.execute("SELECT COUNT(*) as total FROM rental_reports WHERE report_type = 'vacate' AND status IN ('open', 'in_progress')")
        stats['pending_vacate_notices'] = cursor.fetchone()['total'] or 0
        
        # Recent bookings (last 5)
        cursor.execute("""
            SELECT b.*, p.title as property_title, p.property_type,
                   COALESCE(u.full_name, b.guest_name) as customer_name
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            ORDER BY b.created_at DESC
            LIMIT 5
        """)
        recent_bookings = cursor.fetchall()
        
        # Upcoming check-ins - Show all confirmed bookings with future start dates
        # First, let's check ALL confirmed bookings to see what we have
        cursor.execute("""
            SELECT b.id, b.status, b.booking_type, b.start_date, b.end_date,
                   p.title as property_title, p.property_type,
                   CURDATE() as today_date,
                   DATEDIFF(b.start_date, CURDATE()) as days_until_start,
                   DATEDIFF(b.end_date, CURDATE()) as days_until_end
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE b.status = 'confirmed'
            ORDER BY b.start_date ASC
            LIMIT 10
        """)
        all_confirmed = cursor.fetchall()
        
        # Debug: Show all confirmed bookings first
        print(f"\n=== DEBUG Manager Dashboard - All Confirmed Bookings ===")
        print(f"Total confirmed bookings found: {len(all_confirmed)}")
        for b in all_confirmed:
            print(f"  Booking ID {b['id']}:")
            print(f"    status='{b.get('status')}', booking_type='{b.get('booking_type')}', property_type='{b.get('property_type')}'")
            print(f"    start_date={b.get('start_date')}, end_date={b.get('end_date')}")
            print(f"    today={b.get('today_date')}, days_until_start={b.get('days_until_start')}, days_until_end={b.get('days_until_end')}")
            print(f"    title='{b.get('property_title')}'")
        print("=" * 50)
        
        # Now get bookings with future start dates OR ongoing bookings (start in past, end in future)
        cursor.execute("""
            SELECT b.*, p.title as property_title, p.property_type,
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   DATEDIFF(b.start_date, CURDATE()) as days_until,
                   b.booking_type as b_booking_type,
                   p.property_type as p_property_type
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.status = 'confirmed'
            AND b.start_date IS NOT NULL
            AND (
                b.start_date >= CURDATE()  -- Future check-ins
                OR (b.start_date < CURDATE() AND b.end_date >= CURDATE())  -- Ongoing bookings
            )
            ORDER BY b.start_date ASC
            LIMIT 20
        """)
        all_confirmed_future = cursor.fetchall()
        
        # Filter for AirBnB and Rent bookings
        upcoming_checkins = []
        for booking in all_confirmed_future:
            booking_type = booking.get('b_booking_type', '').lower() if booking.get('b_booking_type') else ''
            property_type = booking.get('p_property_type', '').lower() if booking.get('p_property_type') else ''
            
            if booking_type in ['airbnb', 'rent'] or property_type in ['airbnb', 'rent']:
                upcoming_checkins.append(booking)
        
        # Debug output
        print(f"\n=== DEBUG Manager Dashboard - Upcoming Check-ins ===")
        print(f"Total confirmed bookings with future/ongoing dates: {len(all_confirmed_future)}")
        print(f"Filtered to AirBnB/Rent: {len(upcoming_checkins)}")
        if len(all_confirmed_future) > 0:
            print("\nAll confirmed future/ongoing bookings:")
            for b in all_confirmed_future:
                print(f"  ID {b['id']}: booking_type='{b.get('b_booking_type')}', "
                      f"property_type='{b.get('p_property_type')}', "
                      f"start_date={b.get('start_date')}, end_date={b.get('end_date')}, "
                      f"days_until={b.get('days_until')}, title='{b.get('property_title')}'")
        print("=" * 50)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_dashboard.html', 
                             user=user, 
                             stats=stats,
                             recent_bookings=recent_bookings,
                             upcoming_checkins=upcoming_checkins)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading dashboard', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('manager_dashboard.html', user=user, stats={})

@app.route('/manager/properties')
@manager_required
def manager_properties():
    """Manager view of all properties (view and edit only, no delete)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_properties.html', user=user, properties=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all properties with images
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        properties = cursor.fetchall()
        
        # Process images
        for prop in properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')
            else:
                prop['images'] = []
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_properties.html', user=user, properties=properties)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading properties', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('manager_properties.html', user=user, properties=[])

@app.route('/manager/bookings')
@manager_required
def manager_bookings():
    """Manager view of all bookings (view and update status only, no delete)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_bookings.html', user=user, bookings=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.*, 
                   p.title as property_title, p.property_type, p.city, p.price,
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   COALESCE(u.email, b.guest_email) as customer_email,
                   COALESCE(u.phone, b.guest_phone) as customer_phone,
                   CASE 
                       WHEN b.booking_type = 'airbnb' AND b.start_date IS NOT NULL AND b.end_date IS NOT NULL 
                       THEN DATEDIFF(b.end_date, b.start_date)
                       ELSE 1
                   END as nights,
                   CASE 
                       WHEN b.booking_type = 'airbnb' AND b.start_date IS NOT NULL AND b.end_date IS NOT NULL 
                       THEN p.price * DATEDIFF(b.end_date, b.start_date)
                       ELSE p.price
                   END as total_amount,
                   (SELECT COUNT(*) FROM booking_payments WHERE booking_id = b.id) > 0 as has_payment
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            ORDER BY b.created_at DESC
        """)
        bookings = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_bookings.html', user=user, bookings=bookings)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading bookings', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('manager_bookings.html', user=user, bookings=[])

@app.route('/manager/rentals')
@manager_required
def manager_rentals():
    """Manager view of all rentals (view, assign, payments only, no delete)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_rentals.html', user=user, rentals=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*, 
                   p.title as property_title,
                   p.city as property_city,
                   p.property_type,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            ORDER BY r.created_at DESC
        """)
        rentals = cursor.fetchall()
        
        cursor.execute("""
            SELECT rental_id, SUM(amount) as total_paid
            FROM rental_payments
            GROUP BY rental_id
        """)
        payments = cursor.fetchall()
        payment_map = {row['rental_id']: row['total_paid'] for row in payments}
        
        for rental in rentals:
            rental['total_paid'] = payment_map.get(rental['id'], 0)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_rentals.html', user=user, rentals=rentals)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading rentals', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('manager_rentals.html', user=user, rentals=[])

@app.route('/manager/rentals/<int:rental_id>/payments', methods=['GET', 'POST'])
@manager_required
def manager_rental_payments(rental_id):
    """View payment history or record a payment for a rental"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('manager_rentals'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get rental details
        cursor.execute("""
            SELECT r.*, 
                   p.title as property_title,
                   p.city as property_city,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.id = %s
        """, (rental_id,))
        rental = cursor.fetchone()
        
        if not rental:
            flash('Rental not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_rentals'))
        
        if request.method == 'POST':
            # Record payment
            amount = request.form.get('amount')
            payment_date_str = request.form.get('payment_date')
            payment_method = request.form.get('payment_method', 'mpesa')
            reference = request.form.get('reference', '')
            notes = request.form.get('notes', '')
            
            if not amount:
                flash('Payment amount is required', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('manager_rental_payments', rental_id=rental_id))
            
            payment_date_value = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else date.today()
            period_label = payment_date_value.strftime('%B %Y')
            
            cursor.execute("""
                INSERT INTO rental_payments (
                    rental_id, period_label, amount, payment_date, payment_method, reference, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                rental_id,
                period_label,
                float(amount),
                payment_date_value,
                payment_method,
                reference,
                notes
            ))
            
            # Update rental next_due_date
            next_due_date = add_cycle(payment_date_value, rental.get('payment_cycle', 'monthly'))
            
            cursor.execute("""
                UPDATE rentals
                SET last_payment_date = %s,
                    next_due_date = %s
                WHERE id = %s
            """, (payment_date_value, next_due_date, rental_id))
            
            conn.commit()
            flash('Payment recorded successfully', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_rental_payments', rental_id=rental_id))
        
        # GET request - view payment history
        cursor.execute("""
            SELECT * FROM rental_payments
            WHERE rental_id = %s
            ORDER BY payment_date DESC, created_at DESC
        """, (rental_id,))
        payments = cursor.fetchall()
        
        total_paid = sum(payment.get('amount', 0) for payment in payments)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_rental_payments.html', 
                             user=user, 
                             rental=rental, 
                             payments=payments, 
                             total_paid=total_paid)
    except Exception as e:
        print(f"Error: {e}")
        flash(f'Error: {str(e)}', 'error')
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('manager_rentals'))

@app.route('/manager/rentals/assign-new', methods=['GET', 'POST'])
@manager_required
def manager_assign_new_rental():
    """Directly assign a user to a rental property without a booking - Manager"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('manager_rentals'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            property_id = request.form.get('property_id')
            tenant_id = request.form.get('tenant_id')
            rent_amount = request.form.get('rent_amount')
            deposit_amount = request.form.get('deposit_amount', '0')
            lease_start = request.form.get('lease_start')
            lease_end = request.form.get('lease_end')
            payment_cycle = request.form.get('payment_cycle', 'monthly')
            unit_number = request.form.get('unit_number', '').strip()
            floor_number = request.form.get('floor_number', '').strip()
            door_number = request.form.get('door_number', '').strip()
            building_name = request.form.get('building_name', '').strip()
            block_number = request.form.get('block_number', '').strip()
            notes = request.form.get('notes', '')

            if not property_id or not tenant_id or not rent_amount:
                flash('Property, tenant, and rent amount are required', 'error')
                return redirect(url_for('manager_assign_new_rental'))

            # Check if property exists and is for rent
            cursor.execute("SELECT * FROM properties WHERE id = %s AND property_type = 'rent'", (property_id,))
            property = cursor.fetchone()
            if not property:
                flash('Property not found or not available for rent', 'error')
                return redirect(url_for('manager_assign_new_rental'))

            # Check if tenant exists
            cursor.execute("SELECT * FROM users WHERE id = %s AND role = 'user'", (tenant_id,))
            tenant = cursor.fetchone()
            if not tenant:
                flash('Tenant not found', 'error')
                return redirect(url_for('manager_assign_new_rental'))

            # Check if tenant already has an active rental for this property
            cursor.execute("""
                SELECT * FROM rentals 
                WHERE property_id = %s AND tenant_id = %s AND status = 'active'
            """, (property_id, tenant_id))
            existing_rental = cursor.fetchone()
            if existing_rental:
                flash('This tenant already has an active rental for this property', 'error')
                return redirect(url_for('manager_assign_new_rental'))

            lease_start_date = datetime.strptime(lease_start, '%Y-%m-%d').date() if lease_start and lease_start.strip() else None
            lease_end_date = datetime.strptime(lease_end, '%Y-%m-%d').date() if lease_end and lease_end.strip() else None
            rent_amount_value = float(rent_amount)
            deposit_amount_value = float(deposit_amount) if deposit_amount else 0
            # If no lease start date, set next_due_date to today
            next_due_date = lease_start_date if lease_start_date else date.today()

            cursor.execute("""
                INSERT INTO rentals (
                    property_id, tenant_id, rent_amount, deposit_amount,
                    lease_start, lease_end, payment_cycle, next_due_date,
                    unit_number, floor_number, door_number, building_name, block_number,
                    status, notes, assigned_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
            """, (
                property_id,
                tenant_id,
                rent_amount_value,
                deposit_amount_value,
                lease_start_date,
                lease_end_date,
                payment_cycle,
                next_due_date,
                unit_number if unit_number else None,
                floor_number if floor_number else None,
                door_number if door_number else None,
                building_name if building_name else None,
                block_number if block_number else None,
                notes,
                session.get('user_id')
            ))

            rental_id = cursor.lastrowid

            # Record deposit as payment if provided
            if deposit_amount_value > 0:
                cursor.execute("""
                    INSERT INTO rental_payments (
                        rental_id, period_label, amount, payment_date, 
                        payment_method, reference, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    rental_id,
                    'Security Deposit',
                    deposit_amount_value,
                    lease_start_date if lease_start_date else date.today(),
                    'deposit',
                    'AUTO',
                    'Security deposit - Automatic entry from assignment'
                ))

            conn.commit()
            cursor.close()
            conn.close()

            flash('Tenant successfully assigned to property', 'success')
            return redirect(url_for('manager_rentals'))

        # GET request - show form
        # Get all rental properties
        cursor.execute("""
            SELECT id, title, city, price, units_available,
                   (SELECT COUNT(*) FROM rentals WHERE property_id = p.id AND status = 'active') as occupied_units
            FROM properties p
            WHERE property_type = 'rent' AND status = 'active'
            ORDER BY title
        """)
        properties = cursor.fetchall()

        # Get all users (tenants)
        cursor.execute("""
            SELECT id, username, email, full_name, status
            FROM users
            WHERE role = 'user' AND (status = 'active' OR status IS NULL)
            ORDER BY full_name, username
        """)
        users = cursor.fetchall()

        cursor.close()
        conn.close()

        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }

        return render_template('manager_assign_new_rental.html', 
                             user=user, 
                             properties=properties, 
                             users=users)
    except Exception as e:
        print(f"Error: {e}")
        flash(f'Error: {str(e)}', 'error')
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('manager_rentals'))

@app.route('/manager/reports')
@manager_required
def manager_reports():
    """Manager view of reports (view-only, no analytics)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_reports.html', user=user, reports=[], stats={})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        report_type_filter = request.args.get('type', 'all')
        
        # Build query
        query = """
            SELECT rr.*,
                   r.id as rental_id,
                   p.title as property_title,
                   p.city as property_city,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rental_reports rr
            JOIN rentals r ON rr.rental_id = r.id
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON rr.reported_by = u.id
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND rr.status = %s"
            params.append(status_filter)
        
        if report_type_filter != 'all':
            query += " AND rr.report_type = %s"
            params.append(report_type_filter)
        
        query += " ORDER BY rr.created_at DESC"
        
        cursor.execute(query, params)
        reports = cursor.fetchall()
        
        # Get statistics - filter by report type if specified
        stats_query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_count
            FROM rental_reports
            WHERE 1=1
        """
        stats_params = []
        if report_type_filter != 'all':
            stats_query += " AND report_type = %s"
            stats_params.append(report_type_filter)
        
        cursor.execute(stats_query, stats_params)
        stats = cursor.fetchone() or {}
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_reports.html', 
                             user=user, 
                             reports=reports, 
                             stats=stats,
                             status_filter=status_filter,
                             report_type_filter=report_type_filter)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        status_filter = request.args.get('status', 'all')
        report_type_filter = request.args.get('type', 'all')
        return render_template('manager_reports.html', 
                             user=user, 
                             reports=[], 
                             stats={},
                             status_filter=status_filter,
                             report_type_filter=report_type_filter)
    finally:
        if conn:
            conn.close()

@app.route('/manager/maintenance')
@manager_required
def manager_maintenance():
    """Manager view of maintenance requests (view and update, no close)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('manager_maintenance.html', user=user, reports=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        report_type_filter = request.args.get('type', 'all')
        status_filter = request.args.get('status', 'all')
        
        query = """
            SELECT rr.*, 
                   r.id as rental_id,
                   p.title as property_title,
                   p.city as property_city,
                   u.full_name as reported_by_name,
                   u.email as reported_by_email
            FROM rental_reports rr
            JOIN rentals r ON rr.rental_id = r.id
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON rr.reported_by = u.id
            WHERE 1=1
        """
        params = []
        
        if report_type_filter != 'all':
            query += " AND rr.report_type = %s"
            params.append(report_type_filter)
        
        if status_filter != 'all':
            query += " AND rr.status = %s"
            params.append(status_filter)
        
        query += " ORDER BY rr.created_at DESC"
        
        cursor.execute(query, params)
        reports = cursor.fetchall()
        
        # Get statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_count
            FROM rental_reports
        """)
        stats = cursor.fetchone() or {}
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('manager_maintenance.html', 
                             user=user, 
                             reports=reports,
                             stats=stats,
                             report_type_filter=report_type_filter,
                             status_filter=status_filter)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading maintenance reports', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('manager_maintenance.html', user=user, reports=[])

@app.route('/manager/bookings/<int:booking_id>/update-status', methods=['POST'])
@manager_required
def manager_update_booking_status(booking_id):
    """Manager update booking status (same logic as admin but redirects to manager page)"""
    new_status = request.form.get('status')
    if new_status not in ['pending', 'confirmed', 'cancelled', 'completed']:
        flash('Invalid status', 'error')
        return redirect(url_for('manager_bookings'))
    
    # Prevent manual completion
    if new_status == 'completed':
        flash('Bookings are automatically completed when checkout date passes. Cannot manually set to completed.', 'error')
        return redirect(url_for('manager_bookings'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('manager_bookings'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get the booking details
        cursor.execute("""
            SELECT b.*, p.property_type, p.units_available, p.title as property_title, p.city as property_city
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE b.id = %s
        """, (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_bookings'))
        
        old_status = booking['status']
        property_id = booking['property_id']
        property_type = booking['property_type']
        current_units = booking['units_available'] or 0
        
        # Prevent invalid transitions
        if old_status == 'confirmed' and new_status == 'pending':
            flash('Cannot change confirmed booking back to pending. Use cancelled instead.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_bookings'))
        
        if old_status == 'completed':
            flash('Cannot change status of a completed booking.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_bookings'))
        
        if old_status == 'cancelled' and new_status != 'cancelled':
            flash('Cannot change status of a cancelled booking.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_bookings'))
        
        # Update booking status
        cursor.execute("UPDATE bookings SET status = %s WHERE id = %s", (new_status, booking_id))
        
        # Handle units_available for AirBnB only
        if property_type == 'airbnb':
            if old_status != 'confirmed' and new_status == 'confirmed':
                if current_units > 0:
                    new_units = current_units - 1
                    cursor.execute("UPDATE properties SET units_available = %s WHERE id = %s", (new_units, property_id))
            elif old_status == 'confirmed' and new_status == 'cancelled':
                new_units = current_units + 1
                cursor.execute("UPDATE properties SET units_available = %s WHERE id = %s", (new_units, property_id))
        
        conn.commit()
        
        # Record payment and send email when confirmed (same as admin)
        if old_status != 'confirmed' and new_status == 'confirmed':
            try:
                customer_email = None
                customer_name = None
                
                if booking['user_id']:
                    cursor.execute("SELECT email, full_name, username FROM users WHERE id = %s", (booking['user_id'],))
                    user_info = cursor.fetchone()
                    if user_info:
                        customer_email = user_info['email']
                        customer_name = user_info['full_name'] or user_info.get('username', 'Guest')
                else:
                    customer_email = booking.get('guest_email')
                    customer_name = booking.get('guest_name', 'Guest')
                
                # Record payment for AirBnB
                if booking['booking_type'] == 'airbnb':
                    cursor.execute("SELECT price FROM properties WHERE id = %s", (property_id,))
                    property_data = cursor.fetchone()
                    price_per_night = property_data['price'] if property_data else 0
                    
                    nights = 1
                    if booking['start_date'] and booking['end_date']:
                        start = booking['start_date']
                        end = booking['end_date']
                        if isinstance(start, str):
                            start = datetime.strptime(start, '%Y-%m-%d').date()
                        if isinstance(end, str):
                            end = datetime.strptime(end, '%Y-%m-%d').date()
                        nights = (end - start).days
                        if nights < 1:
                            nights = 1
                    
                    total_amount = float(price_per_night) * nights
                    payment_date = date.today()
                    
                    # Check if payment already exists
                    cursor.execute("SELECT id FROM booking_payments WHERE booking_id = %s", (booking_id,))
                    existing_payment_id = cursor.fetchone()
                    
                    if existing_payment_id:
                        cursor.execute("""
                            UPDATE booking_payments
                            SET amount = %s, payment_date = %s,
                                start_date = %s, end_date = %s, nights = %s,
                                customer_name = %s, customer_email = %s,
                                payment_method = 'booking_confirmation', reference = %s, notes = %s
                            WHERE booking_id = %s
                        """, (
                            total_amount, payment_date,
                            booking['start_date'], booking['end_date'], nights,
                            customer_name or 'Guest', customer_email or '',
                            f'BOOKING-{booking_id}', f'AirBnB booking confirmed - {nights} night(s)',
                            booking_id
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO booking_payments (
                                booking_id, property_id, amount, payment_date, booking_type,
                                start_date, end_date, nights, customer_name, customer_email,
                                payment_method, reference, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            booking_id, property_id, total_amount, payment_date, 'airbnb',
                            booking['start_date'], booking['end_date'], nights,
                            customer_name or 'Guest', customer_email or '',
                            'booking_confirmation', f'BOOKING-{booking_id}',
                            f'AirBnB booking confirmed - {nights} night(s)'
                        ))
                    conn.commit()
                
                # Send confirmation email
                if customer_email:
                    send_booking_confirmed_email(
                        customer_email, customer_name,
                        booking['property_title'], booking['property_city'],
                        booking['booking_type'], booking['start_date'], booking['end_date']
                    )
            except Exception as e:
                print(f"Error processing booking confirmation: {e}")
        
        cursor.close()
        conn.close()
        
        flash('Booking status updated successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error updating booking status', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
    
    return redirect(url_for('manager_bookings'))

# Manager Financial Reports
@app.route('/manager/reports/financial/revenue')
@manager_required
def manager_financial_revenue_report():
    """Manager view of revenue report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('manager_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                SUM(amount) as total_rental_revenue,
                COUNT(*) as total_payments,
                MONTH(payment_date) as month,
                YEAR(payment_date) as year
            FROM rental_payments
            WHERE payment_date IS NOT NULL
            GROUP BY YEAR(payment_date), MONTH(payment_date)
            ORDER BY year DESC, month DESC
            LIMIT 12
        """)
        rental_revenue = cursor.fetchall()
        
        cursor.execute("SELECT SUM(amount) as total FROM rental_payments WHERE payment_date IS NOT NULL")
        total_rental = cursor.fetchone()['total'] or 0
        
        cursor.execute("""
            SELECT 
                SUM(amount) as total_booking_revenue,
                COUNT(*) as total_bookings
            FROM booking_payments
            WHERE payment_date IS NOT NULL
        """)
        booking_data = cursor.fetchone()
        total_booking_revenue = booking_data['total_booking_revenue'] or 0
        total_bookings = booking_data['total_bookings'] or 0
        total_revenue = (total_rental or 0) + (total_booking_revenue or 0)
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Manager',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_revenue.html', 
                             user=user,
                             rental_revenue=rental_revenue,
                             total_rental=total_rental,
                             booking_revenue=total_booking_revenue,
                             total_bookings=total_bookings,
                             total_revenue=total_revenue)
    except Exception as e:
        flash(f'Error loading revenue report: {str(e)}', 'error')
        return redirect(url_for('manager_reports'))
    finally:
        if conn:
            conn.close()

# Manager report routes - these will show "Access Denied" for now
# Managers can view reports but detailed sub-reports require admin access
# The main manager_reports route above shows maintenance reports which managers can update

@app.route('/manager/reports/<int:report_id>/update', methods=['POST'])
@manager_required
def manager_update_report_status(report_id):
    """Manager update report status (cannot close reports)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('manager_maintenance'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status FROM rental_reports WHERE id = %s", (report_id,))
        current_report = cursor.fetchone()
        
        if not current_report:
            flash('Report not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_maintenance'))
        
        if current_report['status'] == 'closed':
            flash('Cannot update a closed report.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_maintenance'))
        
        status = request.form.get('status')
        resolution_notes = request.form.get('resolution_notes', '')
        
        if not status:
            flash('Status is required', 'error')
            return redirect(url_for('manager_maintenance'))
        
        # Managers cannot close reports
        if status == 'closed':
            flash('Only administrators can close reports.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('manager_maintenance'))
        
        # Update report (managers cannot set cost)
        cursor.execute("""
            UPDATE rental_reports
            SET status = %s,
                resolution_notes = %s,
                updated_at = %s
            WHERE id = %s
        """, (status, resolution_notes if resolution_notes else None, datetime.now(), report_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Report updated successfully!', 'success')
        return redirect(url_for('manager_maintenance'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error updating report', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('manager_maintenance'))

@app.route('/tenant/dashboard')
@login_required
def tenant_dashboard():
    """Tenant/User dashboard"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'User',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template(
            'tenant_dashboard.html',
            user=user,
            properties=[],
            stats={'rentals': 0, 'sales': 0, 'airbnb': 0}
        )
    
    try:
        cursor = conn.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        # Get available properties for tenant to view
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images
            FROM properties p
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT 12
        """)
        properties = cursor.fetchall()
        
        for prop in properties:
            if prop['images']:
                prop['images'] = prop['images'].split(',')[:1]
            else:
                prop['images'] = []
        
        # Get statistics - count properties by type
        cursor.execute("""
            SELECT property_type, COUNT(*) as count 
            FROM properties 
            WHERE status = 'active' 
            GROUP BY property_type
        """)
        type_counts = cursor.fetchall()
        
        stats = {'rentals': 0, 'sales': 0, 'airbnb': 0}
        for row in type_counts:
            if row['property_type'] == 'rent':
                stats['rentals'] = row['count']
            elif row['property_type'] == 'sale':
                stats['sales'] = row['count']
            elif row['property_type'] == 'airbnb':
                stats['airbnb'] = row['count']

        # Active rental info
        active_rental = None
        rental_payments = []
        rental_reports = []

        rental_paid_total = 0

        if user_id:
            cursor.execute("""
                SELECT r.*, p.title as property_title, p.address as property_address, p.city as property_city
                FROM rentals r
                JOIN properties p ON r.property_id = p.id
                WHERE r.tenant_id = %s AND r.status = 'active'
                ORDER BY r.created_at DESC
                LIMIT 1
            """, (user_id,))
            active_rental = cursor.fetchone()

            if active_rental:
                cursor.execute("""
                    SELECT * FROM rental_payments
                    WHERE rental_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (active_rental['id'],))
                rental_payments = cursor.fetchall()
                rental_paid_total = sum(payment.get('amount', 0) for payment in rental_payments)

                cursor.execute("""
                    SELECT * FROM rental_reports
                    WHERE rental_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (active_rental['id'],))
                rental_reports = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template(
            'tenant_dashboard.html',
            user=user,
            properties=properties,
            stats=stats,
            rental=active_rental,
            rental_payments=rental_payments,
            rental_reports=rental_reports,
            rental_paid_total=rental_paid_total
        )
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading dashboard', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'User',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template(
            'tenant_dashboard.html',
            user=user,
            properties=[],
            stats={'rentals': 0, 'sales': 0, 'airbnb': 0},
            rental=None,
            rental_payments=[],
            rental_reports=[],
            rental_paid_total=0
        )

@app.route('/post-property', methods=['GET', 'POST'])
@manager_required
def post_property():
    """Post a new property - Manager and Admin"""
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        property_type = request.form.get('property_type')  # sale, rent, airbnb
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        price = request.form.get('price')
        bedrooms = request.form.get('bedrooms')
        bathrooms = request.form.get('bathrooms')
        area = request.form.get('area')
        units_available = request.form.get('units_available', '1')
        amenities = request.form.get('amenities', '')
        featured = 1 if request.form.get('featured') == '1' else 0
        
        # For AirBnB
        check_in = request.form.get('check_in', '')
        check_out = request.form.get('check_out', '')
        max_guests = request.form.get('max_guests', '')
        
        # Validation
        if not all([title, description, property_type, city, price, units_available]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('post_property'))
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('post_property'))
        
        try:
            cursor = conn.cursor()
            
            # Insert property
            insert_query = """
                INSERT INTO properties 
                (title, description, property_type, address, city, state, zip_code, 
                 price, bedrooms, bathrooms, area, units_available, amenities, check_in, check_out, 
                 max_guests, featured, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
            """
            
            cursor.execute(insert_query, (
                title, description, property_type, address or None, city, state or None, zip_code or None,
                float(price), int(bedrooms) if bedrooms else None, 
                float(bathrooms) if bathrooms else None, float(area) if area else None,
                int(units_available), amenities, check_in or None, check_out or None, 
                int(max_guests) if max_guests else None, featured, datetime.now()
            ))
            
            property_id = cursor.lastrowid
            
            # Handle image uploads
            uploaded_files = request.files.getlist('images')
            image_paths = []
            
            for file in uploaded_files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    image_paths.append(f"uploads/{filename}")
            
            # Insert images
            if image_paths:
                for image_path in image_paths:
                    cursor.execute("""
                        INSERT INTO property_images (property_id, image_path) 
                        VALUES (%s, %s)
                    """, (property_id, image_path))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Property posted successfully!', 'success')
            return redirect(url_for('property_detail', property_id=property_id))
            
        except Error as e:
            conn.rollback()
            print(f"Error: {e}")
            flash('Error posting property', 'error')
            return redirect(url_for('post_property'))
    
    user = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'full_name': session.get('full_name')
    }
    return render_template('post_property.html', user=user)

@app.route('/book-property/<int:property_id>', methods=['GET', 'POST'])
def book_property(property_id):
    """Book a property - Guest booking allowed for all property types (Rent, Sale, AirBnB).
    Users can book without account, but will need account if rental is approved to become tenant."""
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('property_detail', property_id=property_id))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property details
        cursor.execute("""
            SELECT * FROM properties WHERE id = %s AND status = 'active'
        """, (property_id,))
        property = cursor.fetchone()
        
        if not property:
            flash('Property not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('properties'))
        
        # Check if property has available units
        if property.get('units_available', 0) <= 0:
            flash('No units available for this property', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('property_detail', property_id=property_id))
        
        # Allow guest bookings for all property types (rent, sale, airbnb)
        # Users can book without account, but will need account if they become tenants
        user_logged_in = 'user_id' in session
        
        if request.method == 'POST':
            # Get booking data
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            message = request.form.get('message', '')
            booking_type = property['property_type']
            
            # For guest bookings (all types), get contact details
            guest_name = None
            guest_email = None
            guest_phone = None
            user_id = session.get('user_id')
            
            # If not logged in (guest booking), require contact details
            if not user_logged_in:
                guest_name = request.form.get('guest_name', '').strip()
                guest_email = request.form.get('guest_email', '').strip()
                guest_phone = request.form.get('guest_phone', '').strip()
                
                if not guest_name or not guest_email:
                    flash('Name and email are required for booking requests', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('book_property', property_id=property_id))
            
            # Validation
            if property['property_type'] == 'airbnb':
                # AirBnB requires both start and end dates
                if not start_date or not end_date:
                    flash('Check-in and check-out dates are required for AirBnB bookings', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('book_property', property_id=property_id))
                # Validate end_date is after start_date
                if end_date and start_date and end_date <= start_date:
                    flash('Check-out date must be after check-in date', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('book_property', property_id=property_id))
            elif property['property_type'] in ['rent', 'sale']:
                # Rent and Sale only require start_date (booking/viewing date)
                if not start_date:
                    if property['property_type'] == 'sale':
                        flash('Viewing date is required', 'error')
                    else:
                        flash('Booking date is required', 'error')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('book_property', property_id=property_id))
                # For rent/sale, don't set end_date
                end_date = None
            
            # Note: Units will decrease only when admin confirms the booking
            # This allows bookings to be created even if units are 0 (pending confirmation)
            
            # Insert booking
            cursor.execute("""
                INSERT INTO bookings (property_id, user_id, booking_type, start_date, end_date, message, 
                                    guest_name, guest_email, guest_phone, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                property_id,
                user_id,
                booking_type,
                start_date if start_date else None,
                end_date if end_date else None,
                message,
                guest_name if guest_name else None,
                guest_email if guest_email else None,
                guest_phone if guest_phone else None
            ))
            
            booking_id = cursor.lastrowid
            
            # Get customer email and phone for confirmation
            customer_email = None
            customer_name = None
            customer_phone = None
            if user_logged_in:
                cursor.execute("SELECT email, full_name, phone FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if user_info:
                    customer_email = user_info['email']
                    customer_name = user_info['full_name'] or user_info.get('username', 'Guest')
                    customer_phone = user_info.get('phone')
            else:
                customer_email = guest_email
                customer_name = guest_name
                customer_phone = guest_phone
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Send confirmation email to customer
            try:
                send_booking_confirmation_email(
                    customer_email,
                    customer_name,
                    property['title'],
                    property['city'],
                    start_date if start_date else None,
                    end_date if end_date else None,
                    booking_type,
                    booking_id
                )
            except Exception as e:
                print(f"Error sending customer confirmation email: {e}")
                # Don't fail the booking if email fails
            
            # Send notification email to admin
            try:
                send_admin_booking_notification(
                    booking_id,
                    property['title'],
                    property['city'],
                    customer_name,
                    customer_email,
                    customer_phone,
                    booking_type,
                    start_date if start_date else None,
                    end_date if end_date else None,
                    message
                )
            except Exception as e:
                print(f"Error sending admin notification email: {e}")
                # Don't fail the booking if email fails
            
            if not user_logged_in:
                if booking_type == 'rent':
                    flash('Booking request submitted successfully! A confirmation email has been sent to ' + guest_email + '. You will need to create an account if your rental is approved to become a tenant.', 'success')
                elif booking_type == 'sale':
                    flash('Viewing request submitted successfully! A confirmation email has been sent to ' + guest_email + '. We will contact you to schedule a viewing.', 'success')
                else:
                    flash('Booking request submitted successfully! A confirmation email has been sent to ' + guest_email + '. Create an account to track your bookings in the future!', 'success')
            else:
                flash('Booking request submitted successfully! A confirmation email has been sent. The property owner will contact you soon.', 'success')
            return redirect(url_for('property_detail', property_id=property_id))
        
        # GET request - show booking form
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        cursor.close()
        conn.close()
        
        return render_template('book_property.html', property=property, user=user)
        
    except Error as e:
        print(f"Error: {e}")
        flash('Error processing booking request', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('property_detail', property_id=property_id))

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    """Admin bookings management page"""
    if session.get('role') != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Admin',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('admin_bookings.html', user=user, bookings=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Auto-complete bookings where end_date has passed and status is 'confirmed'
        # Also increase units back when auto-completing
        today = date.today()
        cursor.execute("""
            SELECT b.id, b.property_id, p.property_type, p.units_available
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE b.status = 'confirmed' 
            AND b.end_date IS NOT NULL 
            AND b.end_date < %s
        """, (today,))
        bookings_to_complete = cursor.fetchall()
        
        for booking in bookings_to_complete:
            # Update booking status to completed
            cursor.execute("""
                UPDATE bookings 
                SET status = 'completed' 
                WHERE id = %s
            """, (booking['id'],))
            
            # Increase units back for AirBnB properties only (rent properties don't decrease on confirmation)
            if booking['property_type'] == 'airbnb':
                current_units = booking['units_available'] or 0
                new_units = current_units + 1
                cursor.execute("""
                    UPDATE properties 
                    SET units_available = %s 
                    WHERE id = %s
                """, (new_units, booking['property_id']))
                print(f"Auto-completed AirBnB booking #{booking['id']}, increased units from {current_units} to {new_units}")
                print(f"Auto-completed booking #{booking['id']} and increased units from {current_units} to {new_units} for property {booking['property_id']}")
        
        if bookings_to_complete:
            conn.commit()
            print(f"Auto-completed {len(bookings_to_complete)} booking(s) where checkout date has passed")
        
        # Get all bookings with property and user details, including payment status
        cursor.execute("""
            SELECT b.*, 
                   p.title as property_title, 
                   p.address as property_address,
                   p.city as property_city,
                   p.price as property_price,
                   u.username as user_username,
                   u.email as user_email,
                   u.full_name as user_full_name,
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   COALESCE(u.email, b.guest_email) as customer_email,
                   COALESCE(u.username, CONCAT('Guest #', b.id)) as customer_username,
                   CASE WHEN bp.id IS NOT NULL THEN 1 ELSE 0 END as has_payment
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN booking_payments bp ON b.id = bp.booking_id
            ORDER BY b.created_at DESC
        """)
        bookings = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_bookings.html', user=user, bookings=bookings)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading bookings', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('admin_bookings.html', user=user, bookings=[])

@app.route('/admin/bookings/payments')
@admin_required
def admin_booking_payments():
    """View all AirBnB booking payments"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bookings'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all booking payments (primarily AirBnB)
        cursor.execute("""
            SELECT 
                bp.id,
                bp.booking_id,
                bp.amount,
                bp.payment_date,
                bp.payment_method,
                bp.reference,
                bp.notes,
                bp.created_at,
                bp.nights,
                b.booking_type,
                b.status as booking_status,
                COALESCE(bp.start_date, b.start_date) as start_date,
                COALESCE(bp.end_date, b.end_date) as end_date,
                p.title as property_title,
                p.city as property_city,
                COALESCE(bp.customer_name, u.full_name, b.guest_name) as customer_name,
                COALESCE(bp.customer_email, u.email, b.guest_email) as customer_email
            FROM booking_payments bp
            JOIN bookings b ON bp.booking_id = b.id
            JOIN properties p ON bp.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            ORDER BY bp.payment_date DESC, bp.created_at DESC
        """)
        payments = cursor.fetchall()
        
        # Get statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(DISTINCT DATE(payment_date)) as payment_days
            FROM booking_payments
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_booking_payments.html', 
                             user=user, 
                             payments=payments,
                             stats=stats)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading booking payments', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/<int:booking_id>/payments', methods=['GET', 'POST'])
@admin_required
def record_booking_payment(booking_id):
    """Manually record a payment for a booking"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bookings'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get booking details
        cursor.execute("""
            SELECT b.*, p.title as property_title, p.price,
                   COALESCE(u.full_name, b.guest_name) as customer_name,
                   COALESCE(u.email, b.guest_email) as customer_email
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.id = %s
        """, (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        if request.method == 'POST':
            amount = request.form.get('amount')
            payment_date_str = request.form.get('payment_date')
            payment_method = request.form.get('payment_method', 'manual')
            reference = request.form.get('reference', '')
            notes = request.form.get('notes', '')
            
            if not amount:
                flash('Payment amount is required', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('record_booking_payment', booking_id=booking_id))
            
            payment_date_value = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else date.today()
            amount_value = float(amount)
            
            # Calculate nights for AirBnB
            nights = 1
            if booking['booking_type'] == 'airbnb' and booking['start_date'] and booking['end_date']:
                nights = (booking['end_date'] - booking['start_date']).days
                if nights < 1:
                    nights = 1
            
            # Check if payment already exists
            cursor.execute("SELECT id FROM booking_payments WHERE booking_id = %s", (booking_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing payment
                cursor.execute("""
                    UPDATE booking_payments
                    SET amount = %s,
                        payment_date = %s,
                        payment_method = %s,
                        reference = %s,
                        notes = %s
                    WHERE booking_id = %s
                """, (amount_value, payment_date_value, payment_method, reference, notes, booking_id))
                flash('Payment updated successfully', 'success')
            else:
                # Insert new payment
                cursor.execute("""
                    INSERT INTO booking_payments (
                        booking_id, property_id, amount, payment_date, booking_type,
                        start_date, end_date, nights, customer_name, customer_email,
                        payment_method, reference, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    booking_id,
                    booking['property_id'],
                    amount_value,
                    payment_date_value,
                    booking['booking_type'],
                    booking['start_date'],
                    booking['end_date'],
                    nights,
                    booking['customer_name'] or 'Guest',
                    booking['customer_email'] or '',
                    payment_method,
                    reference,
                    notes
                ))
                flash('Payment recorded successfully', 'success')
            
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_booking_payments'))
        
        # GET request - show form
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        # Check if payment exists
        cursor.execute("SELECT * FROM booking_payments WHERE booking_id = %s", (booking_id,))
        existing_payment = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        today_str = date.today().strftime('%Y-%m-%d')
        
        return render_template('admin_record_booking_payment.html',
                             user=user,
                             booking=booking,
                             existing_payment=existing_payment,
                             today=today_str)
    except Error as e:
        print(f"Error: {e}")
        flash('Error processing payment', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/<int:booking_id>/update-status', methods=['POST'])
@login_required
def update_booking_status(booking_id):
    """Update booking status"""
    if session.get('role') != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    new_status = request.form.get('status')
    if new_status not in ['pending', 'confirmed', 'cancelled', 'completed']:
        flash('Invalid status', 'error')
        return redirect(url_for('admin_bookings'))
    
    # Prevent manual completion - it should be automatic
    if new_status == 'completed':
        flash('Bookings are automatically completed when checkout date passes. Cannot manually set to completed.', 'error')
        return redirect(url_for('admin_bookings'))
    
    # Prevent manual completion - it should be automatic
    if new_status == 'completed':
        flash('Bookings are automatically completed when checkout date passes. Cannot manually set to completed.', 'error')
        return redirect(url_for('admin_bookings'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bookings'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get the booking details to check property and old status
        cursor.execute("""
            SELECT b.*, p.property_type, p.units_available, p.title as property_title, p.city as property_city
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE b.id = %s
        """, (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        old_status = booking['status']
        property_id = booking['property_id']
        property_type = booking['property_type']
        current_units = booking['units_available'] or 0
        property_title = booking['property_title']
        property_city = booking['property_city']
        
        # Update booking status
        cursor.execute("""
            UPDATE bookings SET status = %s WHERE id = %s
        """, (new_status, booking_id))
        
        # Prevent invalid status transitions
        # Once confirmed, can only go to cancelled (not back to pending, and completed is automatic)
        if old_status == 'confirmed' and new_status == 'pending':
            flash('Cannot change confirmed booking back to pending. Use cancelled instead.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        # Once completed, cannot change status (completed is automatic only)
        if old_status == 'completed':
            flash('Cannot change status of a completed booking. Completed status is set automatically when checkout date passes.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        # Once cancelled, cannot change status
        if old_status == 'cancelled' and new_status != 'cancelled':
            flash('Cannot change status of a cancelled booking.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        # Handle units_available for AirBnB properties only
        # For AirBnB: reduce units when confirmed
        # For Rent: units are reduced when rental is assigned (not when booking is confirmed)
        # For Sale: units are reduced when property is marked as "sold" (not when viewing is confirmed)
        if property_type == 'airbnb':
            # If changing from pending/other to confirmed, decrease units
            if old_status != 'confirmed' and new_status == 'confirmed':
                if current_units > 0:
                    new_units = current_units - 1
                    cursor.execute("""
                        UPDATE properties 
                        SET units_available = %s 
                        WHERE id = %s
                    """, (new_units, property_id))
                    print(f"Decreased units_available from {current_units} to {new_units} for property {property_id}")
                else:
                    flash('Warning: Property has no available units, but booking was confirmed.', 'warning')
            
            # If changing from confirmed to cancelled, increase units back
            elif old_status == 'confirmed' and new_status == 'cancelled':
                new_units = current_units + 1
                cursor.execute("""
                    UPDATE properties 
                    SET units_available = %s 
                    WHERE id = %s
                """, (new_units, property_id))
                print(f"Increased units_available from {current_units} to {new_units} for property {property_id}")
            
            # If changing from confirmed to completed, increase units back (checkout completed)
            elif old_status == 'confirmed' and new_status == 'completed':
                new_units = current_units + 1
                cursor.execute("""
                    UPDATE properties 
                    SET units_available = %s 
                    WHERE id = %s
                """, (new_units, property_id))
                print(f"Increased units_available from {current_units} to {new_units} for property {property_id} (checkout completed)")
        
        conn.commit()
        
        # Record payment and send confirmation email when booking is confirmed
        if old_status != 'confirmed' and new_status == 'confirmed':
            try:
                # Get customer email and name
                customer_email = None
                customer_name = None
                
                if booking['user_id']:
                    # Registered user
                    cursor.execute("SELECT email, full_name, username FROM users WHERE id = %s", (booking['user_id'],))
                    user_info = cursor.fetchone()
                    if user_info:
                        customer_email = user_info['email']
                        customer_name = user_info['full_name'] or user_info.get('username', 'Guest')
                else:
                    # Guest booking
                    customer_email = booking.get('guest_email')
                    customer_name = booking.get('guest_name', 'Guest')
                
                # Record payment for confirmed bookings (especially AirBnB)
                if booking['booking_type'] == 'airbnb':
                    # Calculate payment amount and nights
                    cursor.execute("SELECT price FROM properties WHERE id = %s", (property_id,))
                    property_data = cursor.fetchone()
                    price_per_night = property_data['price'] if property_data else 0
                    
                    nights = 1  # Default to 1 night
                    if booking['start_date'] and booking['end_date']:
                        start = booking['start_date']
                        end = booking['end_date']
                        if isinstance(start, str):
                            start = datetime.strptime(start, '%Y-%m-%d').date()
                        if isinstance(end, str):
                            end = datetime.strptime(end, '%Y-%m-%d').date()
                        nights = (end - start).days
                        if nights < 1:
                            nights = 1
                    
                    total_amount = float(price_per_night) * nights
                    payment_date = date.today()
                    
                    # Record the payment
                    cursor.execute("""
                        INSERT INTO booking_payments (
                            booking_id, property_id, amount, payment_date, booking_type,
                            start_date, end_date, nights, customer_name, customer_email,
                            payment_method, reference, notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        booking_id,
                        property_id,
                        total_amount,
                        payment_date,
                        'airbnb',
                        booking['start_date'],
                        booking['end_date'],
                        nights,
                        customer_name or 'Guest',
                        customer_email or '',
                        'booking_confirmation',
                        f'BOOKING-{booking_id}',
                        f'AirBnB booking confirmed - {nights} night(s)'
                    ))
                    print(f"Recorded payment of KSH {total_amount:,.2f} for booking #{booking_id} ({nights} nights)")
                elif booking['booking_type'] in ['rent', 'sale']:
                    # For rent/sale viewings, record a minimal payment entry (viewing fee if applicable)
                    # Or skip payment recording for viewings - they're just viewing requests
                    # For now, we'll skip payment recording for rent/sale viewings
                    pass
                
                # Send confirmation email
                if customer_email:
                    send_booking_confirmed_email(
                        customer_email,
                        customer_name,
                        property_title,
                        property_city,
                        booking['booking_type'],
                        booking['start_date'],
                        booking['end_date']
                    )
                    print(f"Sent confirmation email to {customer_email} for booking #{booking_id}")
                else:
                    print(f"Warning: No email found for booking #{booking_id}, skipping confirmation email")
            except Exception as e:
                print(f"Error processing booking confirmation: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the status update if payment/email fails
        
        cursor.close()
        conn.close()
        
        flash('Booking status updated successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error updating booking status', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
    
    return redirect(url_for('admin_bookings'))

@app.route('/admin/rentals')
@admin_required
def admin_rentals():
    """Admin rentals overview"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_rentals.html', user=session.get('user'), rentals=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*, 
                   p.title as property_title,
                   p.address as property_address,
                   p.city as property_city,
                   p.property_type,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            ORDER BY r.created_at DESC
        """)
        rentals = cursor.fetchall()

        cursor.execute("""
            SELECT rental_id, SUM(amount) as total_paid
            FROM rental_payments
            GROUP BY rental_id
        """)
        payments = cursor.fetchall()
        payment_map = {row['rental_id']: row['total_paid'] for row in payments}

        cursor.execute("""
            SELECT rental_id, COUNT(*) as open_reports
            FROM rental_reports
            WHERE status IN ('open', 'in_progress')
            GROUP BY rental_id
        """)
        reports = cursor.fetchall()
        report_map = {row['rental_id']: row['open_reports'] for row in reports}

        for rental in rentals:
            rental['total_paid'] = payment_map.get(rental['id'], 0)
            rental['open_reports'] = report_map.get(rental['id'], 0)

        cursor.close()
        conn.close()

        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }

        today_str = date.today().strftime('%Y-%m-%d')
        return render_template('admin_rentals.html', user=user, rentals=rentals, today=today_str)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading rentals', 'error')
        if conn:
            cursor.close()
            conn.close()
        return render_template('admin_rentals.html', user=session.get('user'), rentals=[], today=date.today().strftime('%Y-%m-%d'))

@app.route('/admin/rentals/assign-new', methods=['GET', 'POST'])
@admin_required
def assign_new_rental():
    """Directly assign a user to a rental property without a booking"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_rentals'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            property_id = request.form.get('property_id')
            tenant_id = request.form.get('tenant_id')
            rent_amount = request.form.get('rent_amount')
            deposit_amount = request.form.get('deposit_amount', '0')
            lease_start = request.form.get('lease_start')
            lease_end = request.form.get('lease_end')
            payment_cycle = request.form.get('payment_cycle', 'monthly')
            unit_number = request.form.get('unit_number', '').strip()
            floor_number = request.form.get('floor_number', '').strip()
            door_number = request.form.get('door_number', '').strip()
            building_name = request.form.get('building_name', '').strip()
            block_number = request.form.get('block_number', '').strip()
            notes = request.form.get('notes', '')

            if not property_id or not tenant_id or not rent_amount:
                flash('Property, tenant, and rent amount are required', 'error')
                return redirect(url_for('assign_new_rental'))

            # Check if property exists and is for rent
            cursor.execute("SELECT * FROM properties WHERE id = %s AND property_type = 'rent'", (property_id,))
            property = cursor.fetchone()
            if not property:
                flash('Property not found or not available for rent', 'error')
                return redirect(url_for('assign_new_rental'))

            # Check if tenant exists
            cursor.execute("SELECT * FROM users WHERE id = %s AND role = 'user'", (tenant_id,))
            tenant = cursor.fetchone()
            if not tenant:
                flash('Tenant not found', 'error')
                return redirect(url_for('assign_new_rental'))

            # Check if tenant already has an active rental for this property
            cursor.execute("""
                SELECT * FROM rentals 
                WHERE property_id = %s AND tenant_id = %s AND status = 'active'
            """, (property_id, tenant_id))
            existing_rental = cursor.fetchone()
            if existing_rental:
                flash('This tenant already has an active rental for this property', 'error')
                return redirect(url_for('assign_new_rental'))

            lease_start_date = datetime.strptime(lease_start, '%Y-%m-%d').date() if lease_start and lease_start.strip() else None
            lease_end_date = datetime.strptime(lease_end, '%Y-%m-%d').date() if lease_end and lease_end.strip() else None
            rent_amount_value = float(rent_amount)
            deposit_amount_value = float(deposit_amount) if deposit_amount else 0
            # If no lease start date, set next_due_date to today
            next_due_date = lease_start_date if lease_start_date else date.today()

            cursor.execute("""
                INSERT INTO rentals (
                    property_id, tenant_id, rent_amount, deposit_amount,
                    lease_start, lease_end, payment_cycle, next_due_date,
                    unit_number, floor_number, door_number, building_name, block_number,
                    status, notes, assigned_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
            """, (
                property_id,
                tenant_id,
                rent_amount_value,
                deposit_amount_value,
                lease_start_date,
                lease_end_date,
                payment_cycle,
                next_due_date,
                unit_number if unit_number else None,
                floor_number if floor_number else None,
                door_number if door_number else None,
                building_name if building_name else None,
                block_number if block_number else None,
                notes,
                session.get('user_id')
            ))

            rental_id = cursor.lastrowid

            # Record deposit as payment if provided
            if deposit_amount_value > 0:
                cursor.execute("""
                    INSERT INTO rental_payments (
                        rental_id, period_label, amount, payment_date, 
                        payment_method, reference, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    rental_id,
                    'Security Deposit',
                    deposit_amount_value,
                    lease_start_date,
                    'deposit',
                    'AUTO',
                    'Security deposit - Automatic entry from assignment'
                ))

            conn.commit()
            cursor.close()
            conn.close()

            flash('Tenant successfully assigned to property', 'success')
            return redirect(url_for('admin_rentals'))

        # GET request - show form
        # Get all rental properties
        cursor.execute("""
            SELECT id, title, city, price, units_available,
                   (SELECT COUNT(*) FROM rentals WHERE property_id = p.id AND status = 'active') as occupied_units
            FROM properties p
            WHERE property_type = 'rent' AND status = 'active'
            ORDER BY title
        """)
        properties = cursor.fetchall()

        # Get all users (tenants)
        cursor.execute("""
            SELECT id, username, email, full_name, status
            FROM users
            WHERE role = 'user' AND (status = 'active' OR status IS NULL)
            ORDER BY full_name, username
        """)
        users = cursor.fetchall()

        cursor.close()
        conn.close()

        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }

        return render_template('admin_assign_new_rental.html', 
                             user=user, 
                             properties=properties, 
                             users=users)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading assignment form', 'error')
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_rentals'))

@app.route('/admin/rentals/assign/<int:booking_id>', methods=['GET', 'POST'])
@admin_required
def assign_rental(booking_id):
    """Convert a confirmed booking into an active rental"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bookings'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.*, 
                   p.title as property_title,
                   p.address as property_address,
                   p.city as property_city,
                   p.price as property_price,
                   u.full_name as tenant_name,
                   u.email as tenant_email
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.id = %s
        """, (booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash('Booking not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        # Check if booking is for rent
        if booking['booking_type'] != 'rent':
            flash('Only rental bookings can be assigned', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))
        
        # Check if booking was made by a logged-in user (not a guest)
        if not booking.get('user_id') or not booking.get('tenant_name'):
            flash('Cannot assign rental to guest bookings. The customer must create an account first. Please contact them to create an account, then you can assign the rental.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_bookings'))

        if request.method == 'POST':
            rent_amount = request.form.get('rent_amount')
            deposit_amount = request.form.get('deposit_amount', '0')
            lease_start = request.form.get('lease_start')
            lease_end = request.form.get('lease_end')
            payment_cycle = request.form.get('payment_cycle', 'monthly')
            unit_number = request.form.get('unit_number', '').strip()
            floor_number = request.form.get('floor_number', '').strip()
            door_number = request.form.get('door_number', '').strip()
            building_name = request.form.get('building_name', '').strip()
            block_number = request.form.get('block_number', '').strip()
            notes = request.form.get('notes', '')

            if not rent_amount or not lease_start:
                flash('Rent amount and lease start date are required', 'error')
                return redirect(url_for('assign_rental', booking_id=booking_id))

            lease_start_date = datetime.strptime(lease_start, '%Y-%m-%d').date()
            lease_end_date = datetime.strptime(lease_end, '%Y-%m-%d').date() if lease_end else None
            rent_amount_value = float(rent_amount)
            deposit_amount_value = float(deposit_amount) if deposit_amount else 0
            next_due_date = lease_start_date

            cursor.execute("""
                INSERT INTO rentals (
                    booking_id, property_id, tenant_id, rent_amount, deposit_amount,
                    lease_start, lease_end, payment_cycle, next_due_date,
                    unit_number, floor_number, door_number, building_name, block_number,
                    status, notes, assigned_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
            """, (
                booking_id,
                booking['property_id'],
                booking['user_id'],
                rent_amount_value,
                deposit_amount_value,
                lease_start_date,
                lease_end_date,
                payment_cycle,
                next_due_date,
                unit_number if unit_number else None,
                floor_number if floor_number else None,
                door_number if door_number else None,
                building_name if building_name else None,
                block_number if block_number else None,
                notes,
                session.get('user_id')
            ))

            rental_id = cursor.lastrowid

            # Update booking status to confirmed
            if booking['status'] != 'confirmed':
                cursor.execute("""
                    UPDATE bookings SET status = 'confirmed'
                    WHERE id = %s
                """, (booking_id,))

            # Reduce units_available when rental is assigned (for rent properties only)
            cursor.execute("""
                SELECT units_available FROM properties WHERE id = %s
            """, (booking['property_id'],))
            property_data = cursor.fetchone()
            if property_data and property_data['units_available'] > 0:
                new_units = property_data['units_available'] - 1
                cursor.execute("""
                    UPDATE properties 
                    SET units_available = %s 
                    WHERE id = %s
                """, (new_units, booking['property_id']))
                print(f"Decreased units_available from {property_data['units_available']} to {new_units} for property {booking['property_id']} (rental assigned)")

            # Optional: record deposit as payment
            if deposit_amount_value > 0:
                cursor.execute("""
                    INSERT INTO rental_payments (
                        rental_id, period_label, amount, payment_date, payment_method, reference, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    rental_id,
                    'Security Deposit',
                    deposit_amount_value,
                    lease_start_date,
                    'deposit',
                    '',
                    'Automatic entry from assignment'
                ))

            conn.commit()
            cursor.close()
            conn.close()

            flash('Tenant successfully assigned to property', 'success')
            return redirect(url_for('admin_rentals'))

        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }

        cursor.close()
        conn.close()
        return render_template('admin_assign_rental.html', user=user, booking=booking)
    except Error as e:
        print(f"Error: {e}")
        flash('Error assigning rental', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_bookings'))

@app.route('/admin/rentals/<int:rental_id>/payments', methods=['GET', 'POST'])
@admin_required
def record_rental_payment(rental_id):
    """View payment history or record a rental payment"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_rentals'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*, 
                   p.title as property_title,
                   p.city as property_city,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.id = %s
        """, (rental_id,))
        rental = cursor.fetchone()

        if not rental:
            flash('Rental not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_rentals'))

        if request.method == 'POST':
            # Record payment
            amount = request.form.get('amount')
            payment_date_str = request.form.get('payment_date')
            payment_method = request.form.get('payment_method', 'manual')
            reference = request.form.get('reference', '')
            notes = request.form.get('notes', '')

            if not amount:
                flash('Payment amount is required', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('record_rental_payment', rental_id=rental_id))

            payment_date_value = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else date.today()
            period_label = payment_date_value.strftime('%B %Y')

            cursor.execute("""
                INSERT INTO rental_payments (
                    rental_id, period_label, amount, payment_date, payment_method, reference, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                rental_id,
                period_label,
                float(amount),
                payment_date_value,
                payment_method,
                reference,
                notes
            ))

            next_due_date = add_cycle(payment_date_value, rental.get('payment_cycle', 'monthly'))
            cursor.execute("""
                UPDATE rentals
                SET last_payment_date = %s,
                    next_due_date = %s
                WHERE id = %s
            """, (payment_date_value, next_due_date, rental_id))

            conn.commit()
            flash('Payment recorded successfully', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('record_rental_payment', rental_id=rental_id))

        # GET request - view payment history
        cursor.execute("""
            SELECT * FROM rental_payments
            WHERE rental_id = %s
            ORDER BY payment_date DESC, created_at DESC
        """, (rental_id,))
        payments = cursor.fetchall()

        total_paid = sum(payment.get('amount', 0) for payment in payments)

        cursor.close()
        conn.close()

        user = {
            'id': session.get('user_id'),
            'username': session.get('username') or 'Admin',
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }

        return render_template('admin_rental_payments.html', 
                             user=user, 
                             rental=rental, 
                             payments=payments, 
                             total_paid=total_paid)
    except Exception as e:
        print(f"Error: {e}")
        flash(f'Error: {str(e)}', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_rentals'))

@app.route('/admin/rentals/<int:rental_id>/end', methods=['POST'])
@admin_required
def end_rental(rental_id):
    """End a rental (mark as inactive) and increase units_available"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_rentals'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get rental details
        cursor.execute("""
            SELECT r.*, p.units_available, p.property_type
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            WHERE r.id = %s
        """, (rental_id,))
        rental = cursor.fetchone()
        
        if not rental:
            flash('Rental not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_rentals'))
        
        if rental['status'] != 'active':
            flash('Only active rentals can be ended', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_rentals'))
        
        # Update rental status to inactive
        cursor.execute("""
            UPDATE rentals 
            SET status = 'inactive', updated_at = %s
            WHERE id = %s
        """, (datetime.now(), rental_id))
        
        # Increase units_available for the property
        current_units = rental['units_available'] or 0
        new_units = current_units + 1
        cursor.execute("""
            UPDATE properties 
            SET units_available = %s 
            WHERE id = %s
        """, (new_units, rental['property_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'Rental ended successfully. Unit is now available. (Units increased from {current_units} to {new_units})', 'success')
        return redirect(url_for('admin_rentals'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error ending rental', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('admin_rentals'))

@app.route('/tenant/rental/request-vacate', methods=['GET', 'POST'])
@login_required
def request_vacate():
    """Tenant requests to vacate their rental - form and submission"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('tenant_dashboard'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        # Get active rental for the user
        cursor.execute("""
            SELECT r.*, p.title as property_title, p.address as property_address, p.city as property_city
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            WHERE r.tenant_id = %s AND r.status = 'active'
            ORDER BY r.created_at DESC
            LIMIT 1
        """, (user_id,))
        rental = cursor.fetchone()
        
        if not rental:
            flash('No active rental found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('tenant_dashboard'))
        
        if request.method == 'POST':
            vacate_date_str = request.form.get('vacate_date')
            reason = request.form.get('reason', '').strip()
            
            if not vacate_date_str:
                flash('Vacate date is required', 'error')
                cursor.close()
                conn.close()
                user = {
                    'id': session.get('user_id'),
                    'username': session.get('username'),
                    'role': session.get('role'),
                    'full_name': session.get('full_name')
                }
                return render_template('tenant_vacate_request.html', user=user, rental=rental)
            
            vacate_date = datetime.strptime(vacate_date_str, '%Y-%m-%d').date()
            today = date.today()
            
            # Calculate minimum date (1 month from today) - approximately 30 days
            # For more accurate month calculation, we'll use timedelta with 30 days
            min_vacate_date = today + timedelta(days=30)
            
            if vacate_date < min_vacate_date:
                flash(f'Vacate date must be at least 1 month from today. Minimum date: {min_vacate_date.strftime("%B %d, %Y")}', 'error')
                cursor.close()
                conn.close()
                user = {
                    'id': session.get('user_id'),
                    'username': session.get('username'),
                    'role': session.get('role'),
                    'full_name': session.get('full_name')
                }
                min_vacate_date_str = min_vacate_date.strftime('%Y-%m-%d')
                return render_template('tenant_vacate_request.html', user=user, rental=rental, min_vacate_date=min_vacate_date_str)
            
            # Create a report/request for vacating with details
            description = f"""Vacate Request Details:
- Property: {rental['property_title']}
- Requested Vacate Date: {vacate_date.strftime('%B %d, %Y')}
- Reason: {reason if reason else 'Not provided'}

This request requires admin approval. The tenant has provided 1 month notice as required."""
            
            cursor.execute("""
                INSERT INTO rental_reports (rental_id, reported_by, subject, description, report_type, status)
                VALUES (%s, %s, %s, %s, %s, 'open')
            """, (
                rental['id'],
                user_id,
                f'Request to Vacate Rental - {vacate_date.strftime("%B %d, %Y")}',
                description,
                'vacate'
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'Your vacate request has been submitted for {vacate_date.strftime("%B %d, %Y")}. The admin will review and process your request.', 'success')
            return redirect(url_for('tenant_dashboard'))
        
        # GET request - show form
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        # Calculate minimum vacate date (1 month from today) - approximately 30 days
        today = date.today()
        min_vacate_date = today + timedelta(days=30)
        
        return render_template('tenant_vacate_request.html', user=user, rental=rental, min_vacate_date=min_vacate_date.strftime('%Y-%m-%d'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error processing vacate request', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('tenant_dashboard'))

@app.route('/tenant/payments')
@login_required
def tenant_payments():
    """View all payment history for tenant"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('tenant_dashboard'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        # Get active rental
        cursor.execute("""
            SELECT r.*, p.title as property_title
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            WHERE r.tenant_id = %s AND r.status = 'active'
            ORDER BY r.created_at DESC
            LIMIT 1
        """, (user_id,))
        rental = cursor.fetchone()
        
        if not rental:
            flash('No active rental found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('tenant_dashboard'))
        
        # Get all payments
        cursor.execute("""
            SELECT * FROM rental_payments
            WHERE rental_id = %s
            ORDER BY payment_date DESC, created_at DESC
        """, (rental['id'],))
        payments = cursor.fetchall()
        
        total_paid = sum(payment.get('amount', 0) for payment in payments)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('tenant_payments.html', user=user, rental=rental, payments=payments, total_paid=total_paid)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading payment history', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('tenant_dashboard'))

@app.route('/tenant/maintenance')
@login_required
def tenant_maintenance():
    """View all maintenance requests for tenant"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('tenant_dashboard'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        # Get active rental
        cursor.execute("""
            SELECT r.*, p.title as property_title
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            WHERE r.tenant_id = %s AND r.status = 'active'
            ORDER BY r.created_at DESC
            LIMIT 1
        """, (user_id,))
        rental = cursor.fetchone()
        
        if not rental:
            flash('No active rental found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('tenant_dashboard'))
        
        # Get all reports
        cursor.execute("""
            SELECT * FROM rental_reports
            WHERE rental_id = %s
            ORDER BY created_at DESC
        """, (rental['id'],))
        reports = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('tenant_maintenance.html', user=user, rental=rental, reports=reports)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading maintenance requests', 'error')
        if conn:
            cursor.close()
            conn.close()
        return redirect(url_for('tenant_dashboard'))

@app.route('/tenant/maintenance/submit', methods=['POST'])
@login_required
def submit_maintenance_request():
    """Submit a new maintenance request"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('tenant_maintenance'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        user_id = session.get('user_id')
        rental_id = request.form.get('rental_id')
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        
        if not rental_id or not subject or not description:
            flash('All fields are required', 'error')
            return redirect(url_for('tenant_maintenance'))
        
        # Verify the rental belongs to the current user
        cursor.execute("""
            SELECT r.*, p.title as property_title
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            WHERE r.id = %s AND r.tenant_id = %s AND r.status = 'active'
        """, (rental_id, user_id))
        rental = cursor.fetchone()
        
        if not rental:
            flash('Rental not found or you do not have permission to submit requests for this rental', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('tenant_maintenance'))
        
        # Create maintenance request report
        cursor.execute("""
            INSERT INTO rental_reports (rental_id, reported_by, subject, description, report_type, status)
            VALUES (%s, %s, %s, %s, %s, 'open')
        """, (
            rental_id,
            user_id,
            subject,
            description,
            'maintenance'
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Your maintenance request has been submitted successfully. We will review it and get back to you soon.', 'success')
        return redirect(url_for('tenant_maintenance'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error submitting maintenance request', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('tenant_maintenance'))

@app.route('/tenant/rental/report', methods=['POST'])
@login_required
def submit_rental_report():
    """Tenant submits a rental report/issue"""
    rental_id = request.form.get('rental_id')
    subject = request.form.get('subject')
    description = request.form.get('description')
    report_type = request.form.get('report_type', 'general')

    if not rental_id or not subject:
        flash('Subject is required for reports', 'error')
        return redirect(url_for('tenant_dashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('tenant_dashboard'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM rentals
            WHERE id = %s AND tenant_id = %s
        """, (rental_id, session.get('user_id')))
        rental = cursor.fetchone()

        if not rental:
            flash('Rental not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('tenant_dashboard'))

        cursor.execute("""
            INSERT INTO rental_reports (
                rental_id, reported_by, subject, report_type, description
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            rental_id,
            session.get('user_id'),
            subject,
            report_type,
            description
        ))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Report submitted successfully', 'success')
        return redirect(url_for('tenant_dashboard'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error submitting report', 'error')
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('tenant_dashboard'))

@app.route('/admin/reports')
@admin_required
def admin_reports():
    """View all rental reports - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('admin_reports.html', user=user, reports=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        report_type_filter = request.args.get('type', 'all')
        
        # Build query
        query = """
            SELECT rr.*,
                   r.id as rental_id,
                   p.title as property_title,
                   p.city as property_city,
                   u.full_name as tenant_name,
                   u.email as tenant_email,
                   u.username as tenant_username
            FROM rental_reports rr
            JOIN rentals r ON rr.rental_id = r.id
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON rr.reported_by = u.id
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND rr.status = %s"
            params.append(status_filter)
        
        if report_type_filter != 'all':
            query += " AND rr.report_type = %s"
            params.append(report_type_filter)
        
        query += " ORDER BY rr.created_at DESC"
        
        cursor.execute(query, params)
        reports = cursor.fetchall()
        
        # Get statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_count
            FROM rental_reports
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_reports.html', 
                             user=user, 
                             reports=reports, 
                             stats=stats,
                             status_filter=status_filter,
                             report_type_filter=report_type_filter)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading reports', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('admin_reports.html', user=user, reports=[], stats={})

@app.route('/admin/reports/<int:report_id>/update', methods=['POST'])
@admin_required
def update_report_status(report_id):
    """Update report status and add resolution notes - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if report exists and get current status
        cursor.execute("SELECT status FROM rental_reports WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            flash('Report not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_reports'))
        
        # Prevent updates to closed reports
        if report['status'] == 'closed':
            flash('Cannot update a closed report. It is view-only.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_reports'))
        
        status = request.form.get('status')
        resolution_notes = request.form.get('resolution_notes', '')
        cost = request.form.get('cost', '0')
        
        if not status:
            flash('Status is required', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_reports'))
        
        # Validate and convert cost
        try:
            cost_float = float(cost) if cost else 0.0
            if cost_float < 0:
                cost_float = 0.0
        except (ValueError, TypeError):
            cost_float = 0.0
        
        # Update report
        cursor.execute("""
            UPDATE rental_reports
            SET status = %s,
                resolution_notes = %s,
                cost = %s,
                updated_at = %s
            WHERE id = %s
        """, (status, resolution_notes if resolution_notes else None, cost_float, datetime.now(), report_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Report updated successfully', 'success')
        return redirect(url_for('admin_reports'))
    except Error as e:
        print(f"Error: {e}")
        flash('Error updating report', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_reports'))

# Financial Reports Routes
@app.route('/admin/reports/financial/revenue')
@admin_required
def financial_revenue_report():
    """Revenue report - total income from rentals and bookings"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get rental revenue
        cursor.execute("""
            SELECT 
                SUM(amount) as total_rental_revenue,
                COUNT(*) as total_payments,
                MONTH(payment_date) as month,
                YEAR(payment_date) as year
            FROM rental_payments
            WHERE payment_date IS NOT NULL
            GROUP BY YEAR(payment_date), MONTH(payment_date)
            ORDER BY year DESC, month DESC
            LIMIT 12
        """)
        rental_revenue = cursor.fetchall()
        
        # Get total rental revenue
        cursor.execute("""
            SELECT SUM(amount) as total FROM rental_payments 
            WHERE payment_date IS NOT NULL
        """)
        total_rental = cursor.fetchone()['total'] or 0
        
        # Get booking revenue (from booking_payments table)
        cursor.execute("""
            SELECT 
                SUM(amount) as total_booking_revenue,
                COUNT(*) as total_bookings
            FROM booking_payments
            WHERE payment_date IS NOT NULL
        """)
        booking_data = cursor.fetchone()
        total_booking_revenue = booking_data['total_booking_revenue'] or 0
        total_bookings = booking_data['total_bookings'] or 0
        
        # Get total revenue (rental + booking)
        total_revenue = (total_rental or 0) + (total_booking_revenue or 0)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_revenue.html', 
                             user=user,
                             rental_revenue=rental_revenue,
                             total_rental=total_rental,
                             booking_revenue=total_booking_revenue,
                             total_bookings=total_bookings,
                             total_revenue=total_revenue)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading revenue report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/financial/monthly')
@admin_required
def financial_monthly_report():
    """Monthly financial summary report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get monthly rental revenue
        cursor.execute("""
            SELECT 
                MONTH(payment_date) as month,
                YEAR(payment_date) as year,
                SUM(amount) as rental_revenue,
                COUNT(*) as rental_payments
            FROM rental_payments
            WHERE payment_date IS NOT NULL
            AND payment_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY YEAR(payment_date), MONTH(payment_date)
            ORDER BY year DESC, month DESC
        """)
        monthly_rental = cursor.fetchall()
        
        # Get monthly booking revenue
        cursor.execute("""
            SELECT 
                MONTH(payment_date) as month,
                YEAR(payment_date) as year,
                SUM(amount) as booking_revenue,
                COUNT(*) as booking_payments
            FROM booking_payments
            WHERE payment_date IS NOT NULL
            AND payment_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY YEAR(payment_date), MONTH(payment_date)
            ORDER BY year DESC, month DESC
        """)
        monthly_booking = cursor.fetchall()
        
        # Combine data
        monthly_data = {}
        for row in monthly_rental:
            key = f"{row['year']}-{row['month']:02d}"
            monthly_data[key] = {
                'year': row['year'],
                'month': row['month'],
                'rental_revenue': row['rental_revenue'] or 0,
                'rental_payments': row['rental_payments'],
                'booking_revenue': 0,
                'booking_payments': 0
            }
        
        for row in monthly_booking:
            key = f"{row['year']}-{row['month']:02d}"
            if key in monthly_data:
                monthly_data[key]['booking_revenue'] = row['booking_revenue'] or 0
                monthly_data[key]['booking_payments'] = row['booking_payments']
            else:
                monthly_data[key] = {
                    'year': row['year'],
                    'month': row['month'],
                    'rental_revenue': 0,
                    'rental_payments': 0,
                    'booking_revenue': row['booking_revenue'] or 0,
                    'booking_payments': row['booking_payments']
                }
        
        # Convert to list and calculate totals
        monthly_summary = []
        for key in sorted(monthly_data.keys(), reverse=True):
            data = monthly_data[key]
            data['total_revenue'] = data['rental_revenue'] + data['booking_revenue']
            data['total_payments'] = data['rental_payments'] + data['booking_payments']
            monthly_summary.append(data)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_monthly.html', 
                             user=user,
                             monthly_summary=monthly_summary)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading monthly report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/financial/payments')
@admin_required
def financial_payments_report():
    """Payment history report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                rp.*,
                r.id as rental_id,
                p.title as property_title,
                u.full_name as tenant_name,
                u.email as tenant_email
            FROM rental_payments rp
            JOIN rentals r ON rp.rental_id = r.id
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            ORDER BY rp.payment_date DESC, rp.created_at DESC
            LIMIT 100
        """)
        payments = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_payments.html', user=user, payments=payments)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading payments report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/financial/outstanding')
@admin_required
def financial_outstanding_report():
    """Outstanding payments report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Outstanding payments - rentals with upcoming or past due dates
        cursor.execute("""
            SELECT 
                r.id as rental_id,
                r.rent_amount,
                r.next_due_date,
                r.payment_cycle,
                p.title as property_title,
                u.full_name as tenant_name,
                u.email as tenant_email,
                DATEDIFF(r.next_due_date, CURDATE()) as days_until_due,
                (SELECT COALESCE(SUM(amount), 0) FROM rental_payments WHERE rental_id = r.id AND payment_date IS NOT NULL) as total_paid
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.status = 'active' AND r.next_due_date IS NOT NULL
            ORDER BY r.next_due_date ASC
        """)
        outstanding = cursor.fetchall()
        
        # Calculate total outstanding (simplified - just sum of rent amounts for active rentals)
        cursor.execute("""
            SELECT SUM(rent_amount) as total_outstanding
            FROM rentals
            WHERE status = 'active' AND next_due_date IS NOT NULL
        """)
        result = cursor.fetchone()
        total_outstanding = result['total_outstanding'] or 0 if result else 0
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_outstanding.html', 
                             user=user, 
                             outstanding=outstanding,
                             total_outstanding=total_outstanding)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading outstanding payments report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/financial/yearly')
@admin_required
def financial_yearly_report():
    """Yearly financial summary report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get yearly rental revenue
        cursor.execute("""
            SELECT 
                YEAR(payment_date) as year,
                SUM(amount) as rental_revenue,
                COUNT(*) as rental_payments
            FROM rental_payments
            WHERE payment_date IS NOT NULL
            GROUP BY YEAR(payment_date)
            ORDER BY year DESC
            LIMIT 5
        """)
        yearly_rental = cursor.fetchall()
        
        # Get yearly booking revenue
        cursor.execute("""
            SELECT 
                YEAR(payment_date) as year,
                SUM(amount) as booking_revenue,
                COUNT(*) as booking_payments
            FROM booking_payments
            WHERE payment_date IS NOT NULL
            GROUP BY YEAR(payment_date)
            ORDER BY year DESC
            LIMIT 5
        """)
        yearly_booking = cursor.fetchall()
        
        # Combine data
        yearly_data = {}
        for row in yearly_rental:
            year = row['year']
            yearly_data[year] = {
                'year': year,
                'rental_revenue': row['rental_revenue'] or 0,
                'rental_payments': row['rental_payments'],
                'booking_revenue': 0,
                'booking_payments': 0
            }
        
        for row in yearly_booking:
            year = row['year']
            if year in yearly_data:
                yearly_data[year]['booking_revenue'] = row['booking_revenue'] or 0
                yearly_data[year]['booking_payments'] = row['booking_payments']
            else:
                yearly_data[year] = {
                    'year': year,
                    'rental_revenue': 0,
                    'rental_payments': 0,
                    'booking_revenue': row['booking_revenue'] or 0,
                    'booking_payments': row['booking_payments']
                }
        
        # Convert to list and calculate totals
        yearly_summary = []
        for year in sorted(yearly_data.keys(), reverse=True):
            data = yearly_data[year]
            data['total_revenue'] = data['rental_revenue'] + data['booking_revenue']
            data['total_payments'] = data['rental_payments'] + data['booking_payments']
            yearly_summary.append(data)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/financial_yearly.html', 
                             user=user,
                             yearly_summary=yearly_summary)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading yearly report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/property/occupancy')
@admin_required
def property_occupancy_report():
    """Property occupancy report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.property_type,
                p.city,
                p.price,
                p.units_available,
                COUNT(r.id) as active_rentals,
                (p.units_available - COUNT(r.id)) as available_units,
                CASE 
                    WHEN p.units_available > 0 THEN 
                        ROUND((COUNT(r.id) / p.units_available) * 100, 2)
                    ELSE 0 
                END as occupancy_rate
            FROM properties p
            LEFT JOIN rentals r ON p.id = r.property_id AND r.status = 'active'
            WHERE p.property_type = 'rent' AND p.status = 'active'
            GROUP BY p.id
            ORDER BY occupancy_rate DESC
        """)
        occupancy = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/property_occupancy.html', user=user, occupancy=occupancy)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading occupancy report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/property/maintenance-cost')
@admin_required
def property_maintenance_cost_report():
    """Property maintenance cost report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get maintenance reports grouped by property with costs
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.property_type,
                p.city,
                COUNT(rr.id) as maintenance_count,
                SUM(CASE WHEN rr.report_type = 'maintenance' THEN 1 ELSE 0 END) as maintenance_reports,
                SUM(CASE WHEN rr.status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN rr.status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN rr.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                COALESCE(SUM(rr.cost), 0) as total_cost,
                MAX(rr.created_at) as last_maintenance_date
            FROM properties p
            LEFT JOIN rentals r ON p.id = r.property_id
            LEFT JOIN rental_reports rr ON r.id = rr.rental_id AND rr.report_type = 'maintenance'
            WHERE p.status = 'active'
            GROUP BY p.id
            HAVING maintenance_count > 0
            ORDER BY total_cost DESC, maintenance_count DESC, p.title ASC
        """)
        maintenance_costs = cursor.fetchall()
        
        # Get total maintenance reports count and total cost
        cursor.execute("""
            SELECT 
                COUNT(*) as total_maintenance,
                COALESCE(SUM(cost), 0) as total_maintenance_cost
            FROM rental_reports
            WHERE report_type = 'maintenance'
        """)
        maintenance_stats = cursor.fetchone()
        total_maintenance = maintenance_stats['total_maintenance'] or 0
        total_maintenance_cost = maintenance_stats['total_maintenance_cost'] or 0
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/property_maintenance_cost.html', 
                             user=user, 
                             maintenance_costs=maintenance_costs,
                             total_maintenance=total_maintenance,
                             total_maintenance_cost=total_maintenance_cost)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading maintenance cost report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/property/performance')
@admin_required
def property_performance_report():
    """Property performance report - analyze which properties perform best"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property performance metrics
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.property_type,
                p.city,
                p.price,
                p.units_available,
                -- Booking metrics
                COUNT(DISTINCT b.id) as total_bookings,
                COUNT(DISTINCT CASE WHEN b.status = 'confirmed' THEN b.id END) as confirmed_bookings,
                COUNT(DISTINCT CASE WHEN b.booking_type = 'airbnb' AND b.status = 'confirmed' THEN b.id END) as airbnb_bookings,
                -- Revenue from bookings
                COALESCE(SUM(CASE WHEN bp.amount IS NOT NULL THEN bp.amount ELSE 0 END), 0) as booking_revenue,
                -- Rental metrics
                COUNT(DISTINCT r.id) as total_rentals,
                COUNT(DISTINCT CASE WHEN r.status = 'active' THEN r.id END) as active_rentals,
                -- Revenue from rentals
                COALESCE(SUM(CASE WHEN rp.amount IS NOT NULL THEN rp.amount ELSE 0 END), 0) as rental_revenue,
                -- Maintenance metrics (fewer is better)
                COUNT(DISTINCT CASE WHEN rr.report_type = 'maintenance' THEN rr.id END) as maintenance_requests,
                -- Occupancy rate for rental properties
                CASE 
                    WHEN p.property_type = 'rent' AND p.units_available > 0 THEN
                        ROUND((COUNT(DISTINCT CASE WHEN r.status = 'active' THEN r.id END) / p.units_available) * 100, 2)
                    ELSE NULL
                END as occupancy_rate,
                -- Last booking date
                MAX(b.created_at) as last_booking_date
            FROM properties p
            LEFT JOIN bookings b ON p.id = b.property_id
            LEFT JOIN booking_payments bp ON b.id = bp.booking_id
            LEFT JOIN rentals r ON p.id = r.property_id
            LEFT JOIN rental_payments rp ON r.id = rp.rental_id
            LEFT JOIN rental_reports rr ON r.id = rr.rental_id
            WHERE p.status = 'active'
            GROUP BY p.id
            HAVING COUNT(DISTINCT b.id) > 0 OR COUNT(DISTINCT r.id) > 0
            ORDER BY (COALESCE(SUM(CASE WHEN bp.amount IS NOT NULL THEN bp.amount ELSE 0 END), 0) + COALESCE(SUM(CASE WHEN rp.amount IS NOT NULL THEN rp.amount ELSE 0 END), 0)) DESC, 
                     COUNT(DISTINCT b.id) DESC, 
                     CASE 
                         WHEN p.property_type = 'rent' AND p.units_available > 0 THEN
                             ROUND((COUNT(DISTINCT CASE WHEN r.status = 'active' THEN r.id END) / p.units_available) * 100, 2)
                         ELSE NULL
                     END DESC
        """)
        performance = cursor.fetchall()
        
        # Calculate totals
        total_properties = len(performance)
        total_revenue = sum((p['booking_revenue'] or 0) + (p['rental_revenue'] or 0) for p in performance)
        total_bookings = sum(p['total_bookings'] or 0 for p in performance)
        total_rentals = sum(p['total_rentals'] or 0 for p in performance)
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/property_performance.html', 
                             user=user, 
                             performance=performance,
                             total_properties=total_properties,
                             total_revenue=total_revenue,
                             total_bookings=total_bookings,
                             total_rentals=total_rentals)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading performance report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/property/status')
@admin_required
def property_status_report():
    """Property status report - overview of all property statuses"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get properties grouped by status and type
        cursor.execute("""
            SELECT 
                p.status,
                p.property_type,
                COUNT(*) as property_count,
                SUM(p.units_available) as total_units,
                AVG(p.price) as avg_price,
                MIN(p.price) as min_price,
                MAX(p.price) as max_price
            FROM properties p
            GROUP BY p.status, p.property_type
            ORDER BY p.status, p.property_type
        """)
        status_summary = cursor.fetchall()
        
        # Get detailed property list
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.property_type,
                p.status,
                p.city,
                p.price,
                p.units_available,
                COUNT(DISTINCT b.id) as total_bookings,
                COUNT(DISTINCT r.id) as total_rentals,
                COUNT(DISTINCT CASE WHEN r.status = 'active' THEN r.id END) as active_rentals
            FROM properties p
            LEFT JOIN bookings b ON p.id = b.property_id
            LEFT JOIN rentals r ON p.id = r.property_id
            GROUP BY p.id
            ORDER BY p.status, p.property_type, p.title
        """)
        properties = cursor.fetchall()
        
        # Get status counts
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM properties
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/property_status.html', 
                             user=user, 
                             status_summary=status_summary,
                             properties=properties,
                             status_counts=status_counts)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading property status report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/booking/statistics')
@admin_required
def booking_statistics_report():
    """Booking statistics report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                booking_type,
                status,
                COUNT(*) as count
            FROM bookings
            GROUP BY booking_type, status
        """)
        stats = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as total_bookings
            FROM bookings
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month DESC
        """)
        trends = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/booking_statistics.html', 
                             user=user, 
                             stats=stats,
                             trends=trends)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading booking statistics', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/booking/upcoming')
@admin_required
def booking_upcoming_report():
    """Upcoming bookings report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get upcoming bookings (confirmed bookings with start_date in the future)
        cursor.execute("""
            SELECT 
                b.id,
                b.booking_type,
                b.status,
                b.start_date,
                b.end_date,
                b.created_at,
                COALESCE(u.full_name, b.guest_name) as customer_name,
                COALESCE(u.email, b.guest_email) as customer_email,
                COALESCE(u.phone, b.guest_phone) as customer_phone,
                p.id as property_id,
                p.title as property_title,
                p.property_type,
                p.city,
                p.price,
                CASE 
                    WHEN b.booking_type = 'airbnb' AND b.start_date IS NOT NULL AND b.end_date IS NOT NULL 
                    THEN DATEDIFF(b.end_date, b.start_date)
                    ELSE 1
                END as nights,
                CASE 
                    WHEN b.booking_type = 'airbnb' AND b.start_date IS NOT NULL AND b.end_date IS NOT NULL 
                    THEN p.price * DATEDIFF(b.end_date, b.start_date)
                    ELSE p.price
                END as total_amount,
                DATEDIFF(b.start_date, CURDATE()) as days_until_start,
                COALESCE(SUM(bp.amount), 0) as paid_amount,
                CASE 
                    WHEN COALESCE(SUM(bp.amount), 0) > 0 THEN 'paid'
                    ELSE 'pending'
                END as payment_status
            FROM bookings b
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN properties p ON b.property_id = p.id
            LEFT JOIN booking_payments bp ON b.id = bp.booking_id
            WHERE b.status IN ('pending', 'confirmed')
            AND (
                b.start_date >= CURDATE() 
                OR b.end_date >= CURDATE()
                OR (b.start_date IS NULL AND b.end_date IS NULL)
            )
            GROUP BY b.id
            ORDER BY 
                CASE WHEN b.status = 'confirmed' THEN 0 ELSE 1 END,
                COALESCE(b.start_date, b.end_date, b.created_at) ASC, 
                b.created_at ASC
            LIMIT 100
        """)
        upcoming_bookings = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/booking_upcoming.html', 
                             user=user, 
                             upcoming_bookings=upcoming_bookings)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading upcoming bookings', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/tenant/activity')
@admin_required
def tenant_activity_report():
    """Tenant activity and engagement report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get tenant activity metrics
        cursor.execute("""
            SELECT 
                u.id,
                u.full_name,
                u.email,
                u.username,
                u.created_at as registered_at,
                r.id as rental_id,
                r.rent_amount,
                r.lease_start,
                r.lease_end,
                r.status as rental_status,
                p.title as property_title,
                COUNT(DISTINCT rp.id) as payment_count,
                COALESCE(SUM(rp.amount), 0) as total_paid,
                COUNT(DISTINCT rr.id) as report_count,
                MAX(rp.payment_date) as last_payment_date,
                MAX(rr.created_at) as last_report_date
            FROM users u
            INNER JOIN rentals r ON u.id = r.tenant_id
            LEFT JOIN properties p ON r.property_id = p.id
            LEFT JOIN rental_payments rp ON r.id = rp.rental_id
            LEFT JOIN rental_reports rr ON r.id = rr.rental_id
            WHERE r.status = 'active'
            GROUP BY u.id, r.id
            ORDER BY u.full_name ASC
        """)
        tenant_activity = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/tenant_activity.html', 
                             user=user, 
                             tenant_activity=tenant_activity)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading tenant activity report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/tenant/payment-compliance')
@admin_required
def tenant_payment_compliance_report():
    """Payment compliance report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get payment compliance data
        cursor.execute("""
            SELECT 
                u.id,
                u.full_name,
                u.email,
                r.id as rental_id,
                r.rent_amount,
                r.next_due_date,
                r.payment_cycle,
                p.title as property_title,
                COUNT(DISTINCT rp.id) as total_payments,
                COALESCE(SUM(rp.amount), 0) as total_paid,
                DATEDIFF(r.next_due_date, CURDATE()) as days_until_due,
                CASE 
                    WHEN DATEDIFF(r.next_due_date, CURDATE()) < 0 THEN 'overdue'
                    WHEN DATEDIFF(r.next_due_date, CURDATE()) <= 7 THEN 'due_soon'
                    ELSE 'current'
                END as payment_status
            FROM users u
            INNER JOIN rentals r ON u.id = r.tenant_id
            LEFT JOIN properties p ON r.property_id = p.id
            LEFT JOIN rental_payments rp ON r.id = rp.rental_id AND rp.payment_date IS NOT NULL
            WHERE r.status = 'active'
            GROUP BY u.id, r.id
            ORDER BY 
                CASE payment_status
                    WHEN 'overdue' THEN 1
                    WHEN 'due_soon' THEN 2
                    ELSE 3
                END,
                r.next_due_date ASC
        """)
        payment_compliance = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/tenant_payment_compliance.html', 
                             user=user, 
                             payment_compliance=payment_compliance)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading payment compliance report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/tenant/tenant-list')
@admin_required
def tenant_list_report():
    """Active tenants list report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all active tenants
        cursor.execute("""
            SELECT 
                u.id,
                u.full_name,
                u.email,
                u.username,
                u.phone,
                u.created_at as registered_at,
                r.id as rental_id,
                r.rent_amount,
                r.lease_start,
                r.lease_end,
                r.next_due_date,
                r.payment_cycle,
                r.status as rental_status,
                p.title as property_title,
                p.city as property_city,
                p.property_type,
                DATEDIFF(r.lease_end, CURDATE()) as days_until_lease_end
            FROM users u
            INNER JOIN rentals r ON u.id = r.tenant_id
            LEFT JOIN properties p ON r.property_id = p.id
            WHERE r.status = 'active'
            ORDER BY u.full_name ASC
        """)
        active_tenants = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/tenant_list.html', 
                             user=user, 
                             active_tenants=active_tenants)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading tenant list', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/analytics/overview')
@admin_required
def analytics_overview_report():
    """System overview analytics report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get comprehensive system statistics
        stats = {}
        
        # Property statistics
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE status = 'active'")
        stats['total_properties'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE property_type = 'rent' AND status = 'active'")
        stats['rental_properties'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE property_type = 'sale' AND status = 'active'")
        stats['sale_properties'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM properties WHERE property_type = 'airbnb' AND status = 'active'")
        stats['airbnb_properties'] = cursor.fetchone()['total']
        
        # User statistics
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE status = 'active'")
        stats['total_users'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM rentals WHERE status = 'active'")
        stats['active_rentals'] = cursor.fetchone()['total']
        
        # Booking statistics
        cursor.execute("SELECT COUNT(*) as total FROM bookings")
        stats['total_bookings'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE status = 'confirmed'")
        stats['confirmed_bookings'] = cursor.fetchone()['total']
        
        # Revenue statistics
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM rental_payments WHERE payment_date IS NOT NULL")
        stats['rental_revenue'] = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM booking_payments WHERE payment_date IS NOT NULL")
        stats['booking_revenue'] = cursor.fetchone()['total'] or 0
        stats['total_revenue'] = stats['rental_revenue'] + stats['booking_revenue']
        
        # Report statistics
        cursor.execute("SELECT COUNT(*) as total FROM rental_reports WHERE status IN ('open', 'in_progress')")
        stats['open_reports'] = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/analytics_overview.html', 
                             user=user, 
                             stats=stats)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading analytics overview', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/analytics/trends')
@admin_required
def analytics_trends_report():
    """Trends analysis report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Booking trends by month
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as total_bookings,
                COUNT(CASE WHEN status = 'confirmed' THEN 1 END) as confirmed_bookings,
                COUNT(CASE WHEN booking_type = 'airbnb' THEN 1 END) as airbnb_bookings,
                COUNT(CASE WHEN booking_type = 'rent' THEN 1 END) as rent_bookings,
                COUNT(CASE WHEN booking_type = 'sale' THEN 1 END) as sale_bookings
            FROM bookings
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month DESC
        """)
        booking_trends = cursor.fetchall()
        
        # Combined revenue trends by month
        cursor.execute("""
            SELECT 
                DATE_FORMAT(payment_date, '%Y-%m') as month,
                COALESCE(SUM(amount), 0) as revenue,
                'rental' as source
            FROM rental_payments
            WHERE payment_date >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(payment_date, '%Y-%m')
            UNION ALL
            SELECT 
                DATE_FORMAT(payment_date, '%Y-%m') as month,
                COALESCE(SUM(amount), 0) as revenue,
                'booking' as source
            FROM booking_payments
            WHERE payment_date >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(payment_date, '%Y-%m')
            ORDER BY month DESC
        """)
        all_revenue = cursor.fetchall()
        
        # Combine revenue by month
        revenue_by_month = {}
        for row in all_revenue:
            month = row['month']
            if month not in revenue_by_month:
                revenue_by_month[month] = {'rental': 0, 'booking': 0}
            revenue_by_month[month][row['source']] = row['revenue'] or 0
        
        revenue_trends = []
        for month in sorted(revenue_by_month.keys(), reverse=True):
            revenue_trends.append({
                'month': month,
                'rental_revenue': revenue_by_month[month]['rental'],
                'booking_revenue': revenue_by_month[month]['booking'],
                'total_revenue': revenue_by_month[month]['rental'] + revenue_by_month[month]['booking']
            })
        
        # Property type trends
        cursor.execute("""
            SELECT 
                property_type,
                COUNT(*) as count,
                AVG(price) as avg_price
            FROM properties
            WHERE status = 'active'
            GROUP BY property_type
        """)
        property_type_trends = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/analytics_trends.html', 
                             user=user, 
                             booking_trends=booking_trends,
                             revenue_trends=revenue_trends,
                             property_type_trends=property_type_trends)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading trends analysis', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/analytics/property-popularity')
@admin_required
def analytics_property_popularity_report():
    """Property popularity report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property popularity metrics
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.property_type,
                p.city,
                p.price,
                COUNT(DISTINCT b.id) as total_bookings,
                COUNT(DISTINCT CASE WHEN b.status = 'confirmed' THEN b.id END) as confirmed_bookings,
                COUNT(DISTINCT f.id) as favorite_count,
                COUNT(DISTINCT r.id) as rental_count,
                COALESCE(SUM(bp.amount), 0) as booking_revenue,
                COALESCE(SUM(rp.amount), 0) as rental_revenue,
                MAX(b.created_at) as last_booking_date
            FROM properties p
            LEFT JOIN bookings b ON p.id = b.property_id
            LEFT JOIN booking_payments bp ON b.id = bp.booking_id
            LEFT JOIN rentals r ON p.id = r.property_id
            LEFT JOIN rental_payments rp ON r.id = rp.rental_id
            LEFT JOIN property_favorites f ON p.id = f.property_id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY (COUNT(DISTINCT b.id) + COUNT(DISTINCT f.id) + COUNT(DISTINCT r.id)) DESC, 
                     COUNT(DISTINCT CASE WHEN b.status = 'confirmed' THEN b.id END) DESC
            LIMIT 50
        """)
        popular_properties = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/analytics_property_popularity.html', 
                             user=user, 
                             popular_properties=popular_properties)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading property popularity report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/tenant/lease-expiration')
@admin_required
def tenant_lease_expiration_report():
    """Lease expiration report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_reports'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                r.*,
                p.title as property_title,
                p.city,
                u.full_name as tenant_name,
                u.email as tenant_email,
                DATEDIFF(r.lease_end, CURDATE()) as days_until_expiry
            FROM rentals r
            JOIN properties p ON r.property_id = p.id
            JOIN users u ON r.tenant_id = u.id
            WHERE r.status = 'active' AND r.lease_end IS NOT NULL
            ORDER BY r.lease_end ASC
        """)
        expiring = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('reports/tenant_lease_expiration.html', 
                             user=user, 
                             expiring=expiring)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading lease expiration report', 'error')
        return redirect(url_for('admin_reports'))

@app.route('/admin/properties/<int:property_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_property(property_id):
    """Edit a property - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_properties'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property details - explicitly select columns to ensure units_available is included
        cursor.execute("""
            SELECT id, title, description, property_type, address, city, state, zip_code, 
                   price, bedrooms, bathrooms, area, amenities, units_available, 
                   check_in, check_out, max_guests, status, created_at, updated_at
            FROM properties WHERE id = %s
        """, (property_id,))
        property = cursor.fetchone()
        old_status = property['status'] if property else None
        
        if not property:
            flash('Property not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_properties'))
        
        if request.method == 'POST':
            # Get form data
            title = request.form.get('title')
            description = request.form.get('description')
            property_type = request.form.get('property_type')
            address = request.form.get('address')
            city = request.form.get('city')
            state = request.form.get('state')
            zip_code = request.form.get('zip_code')
            price = request.form.get('price')
            bedrooms = request.form.get('bedrooms')
            bathrooms = request.form.get('bathrooms')
            area = request.form.get('area')
            units_available = request.form.get('units_available', '1') or '1'
            amenities = request.form.get('amenities', '')
            status = request.form.get('status', 'active')
            
            # For AirBnB
            check_in = request.form.get('check_in', '')
            check_out = request.form.get('check_out', '')
            max_guests = request.form.get('max_guests', '')
            
            # Ensure units_available is valid
            try:
                units_available_int = int(units_available)
                if units_available_int < 1:
                    units_available_int = 1
            except (ValueError, TypeError):
                units_available_int = 1
            
            # Validation
            if not all([title, description, property_type, city, price]):
                flash('Please fill in all required fields', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('edit_property', property_id=property_id))
            
            try:
                # Update property
                update_query = """
                    UPDATE properties 
                    SET title = %s, description = %s, property_type = %s, address = %s, 
                        city = %s, state = %s, zip_code = %s, price = %s, bedrooms = %s, 
                        bathrooms = %s, area = %s, units_available = %s, amenities = %s, 
                        check_in = %s, check_out = %s, max_guests = %s, status = %s,
                        updated_at = %s
                    WHERE id = %s
                """
                
                # Check if status is being changed to 'sold' - reduce units_available
                if old_status != 'sold' and status == 'sold':
                    # Reduce units when property is marked as sold
                    if units_available_int > 0:
                        units_available_int = units_available_int - 1
                        print(f"Decreased units_available to {units_available_int} for property {property_id} (marked as sold)")
                
                cursor.execute(update_query, (
                    title, description, property_type, address or None, city, state or None, zip_code or None,
                    float(price), int(bedrooms) if bedrooms else None, 
                    float(bathrooms) if bathrooms else None, float(area) if area else None,
                    units_available_int, amenities, check_in or None, check_out or None, 
                    int(max_guests) if max_guests else None, status, datetime.now(), property_id
                ))
                
                # Handle new image uploads
                uploaded_files = request.files.getlist('images')
                image_paths = []
                
                for file in uploaded_files:
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                        filename = timestamp + filename
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        image_paths.append(f"uploads/{filename}")
                
                # Insert new images
                if image_paths:
                    for image_path in image_paths:
                        cursor.execute("""
                            INSERT INTO property_images (property_id, image_path) 
                            VALUES (%s, %s)
                        """, (property_id, image_path))
                
                # Handle image deletion
                images_to_delete = request.form.getlist('delete_images')
                if images_to_delete:
                    for image_id in images_to_delete:
                        # Get image path before deleting
                        cursor.execute("SELECT image_path FROM property_images WHERE id = %s", (image_id,))
                        img = cursor.fetchone()
                        if img:
                            # Delete file from filesystem
                            file_path = os.path.join('static', img['image_path'])
                            if os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                except:
                                    pass
                        cursor.execute("DELETE FROM property_images WHERE id = %s", (image_id,))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                flash('Property updated successfully!', 'success')
                return redirect(url_for('admin_properties'))
                
            except Error as e:
                conn.rollback()
                print(f"Error: {e}")
                flash('Error updating property', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('edit_property', property_id=property_id))
        
        # GET request - show edit form
        # Get existing images
        cursor.execute("SELECT * FROM property_images WHERE property_id = %s", (property_id,))
        existing_images = cursor.fetchall()
        
        # Convert timedelta objects to time strings for check_in and check_out
        if property.get('check_in') and isinstance(property['check_in'], timedelta):
            # Convert timedelta to time string (HH:MM)
            total_seconds = int(property['check_in'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            property['check_in'] = time(hours, minutes).strftime('%H:%M')
        elif property.get('check_in') and isinstance(property['check_in'], time):
            property['check_in'] = property['check_in'].strftime('%H:%M')
        elif property.get('check_in'):
            # If it's already a string, keep it
            pass
        else:
            property['check_in'] = None
            
        if property.get('check_out') and isinstance(property['check_out'], timedelta):
            # Convert timedelta to time string (HH:MM)
            total_seconds = int(property['check_out'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            property['check_out'] = time(hours, minutes).strftime('%H:%M')
        elif property.get('check_out') and isinstance(property['check_out'], time):
            property['check_out'] = property['check_out'].strftime('%H:%M')
        elif property.get('check_out'):
            # If it's already a string, keep it
            pass
        else:
            property['check_out'] = None
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('edit_property.html', user=user, property=property, existing_images=existing_images)
        
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading property', 'error')
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_properties'))

@app.route('/admin/users')
@admin_required
def admin_users():
    """View all users - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('admin_users.html', user=user, users=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        role_filter = request.args.get('role', 'all')
        status_filter = request.args.get('status', 'all')
        
        # Build query
        query = """
            SELECT id, username, email, full_name, role, status, created_at
            FROM users
            WHERE (status != 'deleted' OR status IS NULL)
        """
        params = []
        
        if role_filter != 'all':
            query += " AND role = %s"
            params.append(role_filter)
        
        if status_filter != 'all':
            if status_filter == 'active':
                query += " AND (status = 'active' OR status IS NULL)"
            else:
                query += " AND status = %s"
                params.append(status_filter)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_users.html', user=user, users=users)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading users', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('admin_users.html', user=user, users=[])

@app.route('/admin/users/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Suspend a user - Admin only"""
    if user_id == session.get('user_id'):
        flash('You cannot suspend your own account', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'suspended' WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User suspended successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error suspending user', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
@admin_required
def activate_user(user_id):
    """Activate a suspended user - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User activated successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error activating user', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (permanent delete) - Admin only"""
    if user_id == session.get('user_id'):
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()

        # Clean up related records to avoid orphaned data
        cursor.execute("UPDATE bookings SET user_id = NULL WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM property_favorites WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM rental_reports WHERE reported_by = %s", (user_id,))
        cursor.execute("DELETE FROM rentals WHERE tenant_id = %s", (user_id,))
        cursor.execute("UPDATE rentals SET assigned_by = NULL WHERE assigned_by = %s", (user_id,))

        # Permanently remove the user record
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User deleted successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error deleting user', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/change-role', methods=['POST'])
@admin_required
def change_user_role(user_id):
    """Change user role - Admin only"""
    if user_id == session.get('user_id'):
        flash('You cannot change your own role', 'error')
        return redirect(url_for('admin_users'))
    
    new_role = request.form.get('role')
    if not new_role or new_role not in ['admin', 'manager', 'user']:
        flash('Invalid role', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User role updated successfully', 'success')
    except Error as e:
        print(f"Error: {e}")
        flash('Error updating user role', 'error')
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
    return redirect(url_for('admin_users'))

@app.route('/admin/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Create a new user account - Admin only"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user')
        
        # Validation
        if not username or not email:
            flash('Username and email are required', 'error')
            return redirect(url_for('create_user'))
        
        if role not in ['admin', 'manager', 'user']:
            role = 'user'
        
        # Generate random password
        temp_password = generate_random_password(12)
        password_hash = generate_password_hash(temp_password)
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('create_user'))
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('create_user'))
            
            # Insert new user
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
            """, (username, email, password_hash, full_name, role))
            
            user_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            # Send account creation email
            try:
                send_account_creation_email(email, username, temp_password, full_name, role)
                flash(f'User account created successfully! Login credentials have been sent to {email}', 'success')
            except Exception as e:
                print(f"Error sending email: {e}")
                flash(f'User account created successfully, but email could not be sent. Temporary password: {temp_password}', 'warning')
            
            return redirect(url_for('admin_users'))
            
        except Error as e:
            print(f"Error: {e}")
            flash('Error creating user account', 'error')
            if conn:
                try:
                    conn.rollback()
                    cursor.close()
                    conn.close()
                except:
                    pass
            return redirect(url_for('create_user'))
    
    # GET request - show form
    user = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'full_name': session.get('full_name')
    }
    return render_template('admin_create_user.html', user=user)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow users to change their password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return redirect(url_for('change_password'))
        
        user_id = session.get('user_id')
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('change_password'))
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Verify current password
            cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user['password_hash'], current_password):
                flash('Current password is incorrect', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('change_password'))
            
            # Update password
            new_password_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_password_hash, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('tenant_dashboard') if session.get('role') == 'user' else url_for('admin_dashboard'))
            
        except Error as e:
            print(f"Error: {e}")
            flash('Error changing password', 'error')
            if conn:
                try:
                    conn.rollback()
                    cursor.close()
                    conn.close()
                except:
                    pass
            return redirect(url_for('change_password'))
    
    # GET request - show form
    user = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'full_name': session.get('full_name')
    }
    return render_template('change_password.html', user=user)

@app.route('/admin/properties/<int:property_id>/delete', methods=['POST'])
@admin_required
def delete_property(property_id):
    """Delete a property - Admin only"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_properties'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property images before deleting
        cursor.execute("SELECT image_path FROM property_images WHERE property_id = %s", (property_id,))
        images = cursor.fetchall()
        
        # Delete property (cascade will delete images from DB)
        cursor.execute("DELETE FROM properties WHERE id = %s", (property_id,))
        
        # Delete image files from filesystem
        for img in images:
            file_path = os.path.join('static', img['image_path'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Property deleted successfully!', 'success')
        return redirect(url_for('admin_properties'))
        
    except Error as e:
        conn.rollback()
        print(f"Error: {e}")
        flash('Error deleting property', 'error')
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return redirect(url_for('admin_properties'))

@app.route('/favicon.ico')
def favicon():
    """Serve favicon using hero image"""
    return send_from_directory('static/uploads', 'hero.jpg', mimetype='image/jpeg')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/my-bookings')
@login_required
def my_bookings():
    """User booking history page"""
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('my_bookings.html', user=user, bookings=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all bookings for this user
        cursor.execute("""
            SELECT b.*, 
                   p.title as property_title,
                   p.city as property_city,
                   p.address as property_address,
                   p.price as property_price,
                   p.property_type,
                   GROUP_CONCAT(pi.image_path) as images
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE b.user_id = %s
            GROUP BY b.id
            ORDER BY b.created_at DESC
        """, (user_id,))
        bookings = cursor.fetchall()
        
        # Process images
        for booking in bookings:
            if booking['images']:
                booking['images'] = booking['images'].split(',')[:1]  # First image only
            else:
                booking['images'] = []
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('my_bookings.html', user=user, bookings=bookings)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading bookings', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('my_bookings.html', user=user, bookings=[])

@app.route('/property/<int:property_id>/availability')
def property_availability(property_id):
    """Get property availability calendar data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get property details
        cursor.execute("SELECT * FROM properties WHERE id = %s", (property_id,))
        property = cursor.fetchone()
        
        if not property:
            return jsonify({'error': 'Property not found'}), 404
        
        # Get all confirmed bookings for this property
        cursor.execute("""
            SELECT start_date, end_date 
            FROM bookings 
            WHERE property_id = %s 
            AND status = 'confirmed'
            AND start_date IS NOT NULL
            AND end_date IS NOT NULL
        """, (property_id,))
        bookings = cursor.fetchall()
        
        # Format booked dates
        booked_dates = []
        for booking in bookings:
            if booking['start_date'] and booking['end_date']:
                start = booking['start_date']
                end = booking['end_date']
                # Generate all dates between start and end
                current_date = start
                while current_date <= end:
                    booked_dates.append(current_date.strftime('%Y-%m-%d'))
                    current_date += timedelta(days=1)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'property_id': property_id,
            'units_available': property.get('units_available', 0) or 0,
            'booked_dates': booked_dates
        })
    except Error as e:
        print(f"Error: {e}")
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return jsonify({'error': 'Error fetching availability'}), 500

@app.route('/favorites')
@login_required
def favorites():
    """User's favorite properties page - Users see only their own favorites"""
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    # If admin, redirect to admin favorites view
    if user_role == 'admin':
        return redirect(url_for('admin_favorites'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('favorites.html', user=user, favorites=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get user's favorite properties
        cursor.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(pi.image_path) as images,
                   pf.created_at as favorited_at
            FROM property_favorites pf
            JOIN properties p ON pf.property_id = p.id
            LEFT JOIN property_images pi ON p.id = pi.property_id
            WHERE pf.user_id = %s
            GROUP BY p.id
            ORDER BY pf.created_at DESC
        """, (user_id,))
        favorites = cursor.fetchall()
        
        # Process images
        for fav in favorites:
            if fav['images']:
                fav['images'] = fav['images'].split(',')[:1]  # First image only
            else:
                fav['images'] = []
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('favorites.html', user=user, favorites=favorites)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading favorites', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('favorites.html', user=user, favorites=[])

@app.route('/favorites/add/<int:property_id>', methods=['POST'])
@login_required
def add_to_favorites(property_id):
    """Add property to favorites"""
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Check if already favorited
        cursor.execute("SELECT id FROM property_favorites WHERE user_id = %s AND property_id = %s", (user_id, property_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Property already in favorites'}), 400
        
        # Add to favorites
        cursor.execute("INSERT INTO property_favorites (user_id, property_id) VALUES (%s, %s)", (user_id, property_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Added to favorites'})
    except Error as e:
        print(f"Error: {e}")
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return jsonify({'success': False, 'message': 'Error adding to favorites'}), 500

@app.route('/favorites/remove/<int:property_id>', methods=['POST'])
@login_required
def remove_from_favorites(property_id):
    """Remove property from favorites"""
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM property_favorites WHERE user_id = %s AND property_id = %s", (user_id, property_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Removed from favorites'})
    except Error as e:
        print(f"Error: {e}")
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return jsonify({'success': False, 'message': 'Error removing from favorites'}), 500

@app.route('/favorites/check/<int:property_id>')
@login_required
def check_favorite(property_id):
    """Check if property is in user's favorites"""
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'is_favorite': False})
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM property_favorites WHERE user_id = %s AND property_id = %s", (user_id, property_id))
        is_favorite = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return jsonify({'is_favorite': is_favorite})
    except Error as e:
        print(f"Error: {e}")
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return jsonify({'is_favorite': False})

@app.route('/admin/favorites')
@admin_required
def admin_favorites():
    """Admin view of all favorites - see which properties are favorited by which users"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        return render_template('admin_favorites.html', user=user, favorites=[], stats={})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all favorites with user and property details
        cursor.execute("""
            SELECT pf.id as favorite_id,
                   pf.created_at as favorited_at,
                   p.id as property_id,
                   p.title as property_title,
                   p.city as property_city,
                   p.property_type,
                   p.price,
                   u.id as user_id,
                   u.username,
                   u.full_name,
                   u.email,
                   COUNT(*) OVER (PARTITION BY p.id) as favorite_count
            FROM property_favorites pf
            JOIN properties p ON pf.property_id = p.id
            JOIN users u ON pf.user_id = u.id
            ORDER BY pf.created_at DESC
        """)
        favorites = cursor.fetchall()
        
        # Get statistics
        cursor.execute("SELECT COUNT(DISTINCT property_id) as total_properties, COUNT(DISTINCT user_id) as total_users, COUNT(*) as total_favorites FROM property_favorites")
        stats = cursor.fetchone()
        
        # Get most favorited properties
        cursor.execute("""
            SELECT p.id, p.title, p.city, p.property_type, COUNT(*) as favorite_count
            FROM property_favorites pf
            JOIN properties p ON pf.property_id = p.id
            GROUP BY p.id
            ORDER BY favorite_count DESC
            LIMIT 10
        """)
        most_favorited = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        
        return render_template('admin_favorites.html', user=user, favorites=favorites, stats=stats, most_favorited=most_favorited)
    except Error as e:
        print(f"Error: {e}")
        flash('Error loading favorites', 'error')
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
        return render_template('admin_favorites.html', user=user, favorites=[], stats={}, most_favorited=[])

# Initialize scheduler for automated reminders
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=check_and_send_reminders,
    trigger=CronTrigger(hour=9, minute=0),  # Run daily at 9 AM
    id='daily_reminders',
    name='Send daily reminders for check-ins, check-outs, payments, and lease expirations',
    replace_existing=True
)

if __name__ == '__main__':
    # Start scheduler
    scheduler.start()
    print("Reminder scheduler started - checking daily at 9:00 AM")
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

