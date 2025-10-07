from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session, make_response
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import os
import socket
import re
import html
import hashlib
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter
from werkzeug.utils import secure_filename
from user_agents import parse
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import csv

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'eeeELLENsoCUTE')
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Security configurations
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour

# Initialize security extensions
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

# Security helper functions
def sanitize_input(text, max_length=1000):
    """Sanitize user input to prevent XSS and limit length"""
    if not text:
        return ""
    
    # Limit length
    text = text[:max_length]
    
    # HTML escape
    text = html.escape(text)
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\']', '', text)
    
    return text.strip()

def validate_email(email):
    """Enhanced email validation"""
    if not email:
        return False
    
    # Basic format check
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    
    # Length check
    if len(email) > 254:
        return False
    
    return True

def validate_url(url):
    """Validate URL format"""
    if not url:
        return True  # Optional field
    
    url_pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
    return bool(re.match(url_pattern, url))

def is_suspicious_content(text):
    """Basic content filtering for spam/suspicious submissions"""
    suspicious_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        r'(?i)(buy|sell|cheap|free|money|cash|loan|credit)',
        r'(?i)(viagra|cialis|pharmacy|drug)',
        r'(?i)(click here|visit now|limited time)',
        r'[^\w\s@.-]',  # Too many special characters
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text):
            return True
    
    return False

# Analytics Functions
def get_visitor_id(request):
    """Create anonymous visitor ID"""
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
    user_agent = request.headers.get('User-Agent', '')
    # Create hash for privacy
    visitor_string = f"{ip}_{user_agent}"
    return hashlib.md5(visitor_string.encode()).hexdigest()[:12]

def track_visit(request):
    """Track page visit"""
    try:
        # Create analytics directory if it doesn't exist
        os.makedirs('analytics', exist_ok=True)
        
        # Parse user agent for device info
        user_agent = parse(request.headers.get('User-Agent', ''))
        
        visit_data = {
            'timestamp': datetime.now().isoformat(),
            'visitor_id': get_visitor_id(request),
            'page': request.path,
            'method': request.method,
            'referrer': request.headers.get('Referer', ''),
            'device': {
                'is_mobile': user_agent.is_mobile,
                'is_tablet': user_agent.is_tablet,
                'is_pc': user_agent.is_pc,
                'browser': user_agent.browser.family,
                'os': user_agent.os.family
            },
            'query_params': dict(request.args)
        }
        
        # Save to daily file
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f'analytics/visits_{today}.json'
        
        with open(filename, 'a') as f:
            f.write(json.dumps(visit_data) + '\n')
            
    except Exception as e:
        # Don't break the site if analytics fails
        print(f"Analytics error: {e}")

def load_analytics_data(days=7):
    """Load analytics data from the last N days"""
    all_visits = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        filename = f'analytics/visits_{date}.json'
        
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    for line in f:
                        if line.strip():
                            all_visits.append(json.loads(line))
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return all_visits

def analyze_data(visits):
    """Analyze visit data and return insights"""
    if not visits:
        return {}
    
    # Basic stats
    total_visits = len(visits)
    unique_visitors = len(set(visit['visitor_id'] for visit in visits))
    
    # Page popularity
    page_views = Counter(visit['page'] for visit in visits)
    
    # Device breakdown
    mobile_visits = sum(1 for visit in visits if visit['device']['is_mobile'])
    tablet_visits = sum(1 for visit in visits if visit['device']['is_tablet'])
    desktop_visits = sum(1 for visit in visits if visit['device']['is_pc'])
    
    # Browser stats
    browsers = Counter(visit['device']['browser'] for visit in visits)
    
    # Hourly traffic
    hourly_traffic = defaultdict(int)
    for visit in visits:
        hour = datetime.fromisoformat(visit['timestamp']).hour
        hourly_traffic[hour] += 1
    
    # Daily traffic
    daily_traffic = defaultdict(int)
    for visit in visits:
        date = datetime.fromisoformat(visit['timestamp']).strftime('%Y-%m-%d')
        daily_traffic[date] += 1
    
    # Referrer analysis
    referrers = []
    for visit in visits:
        ref = visit.get('referrer', '')
        if ref:
            if 'google' in ref.lower():
                referrers.append('Google')
            elif 'facebook' in ref.lower():
                referrers.append('Facebook')
            elif 'instagram' in ref.lower():
                referrers.append('Instagram')
            elif 'twitter' in ref.lower():
                referrers.append('Twitter')
            else:
                referrers.append('Other')
        else:
            referrers.append('Direct')
    
    referrer_stats = Counter(referrers)
    
    return {
        'total_visits': total_visits,
        'unique_visitors': unique_visitors,
        'page_views': dict(page_views.most_common(10)),
        'device_breakdown': {
            'mobile': mobile_visits,
            'tablet': tablet_visits,
            'desktop': desktop_visits
        },
        'browsers': dict(browsers.most_common(5)),
        'hourly_traffic': dict(hourly_traffic),
        'daily_traffic': dict(sorted(daily_traffic.items())),
        'referrers': dict(referrer_stats)
    }

# CSV Export Functions
def export_to_csv(data, filename):
    """Export data to CSV format"""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    if isinstance(data, list) and len(data) > 0:
        # Write headers
        writer.writerow(data[0].keys())
        # Write data
        for row in data:
            writer.writerow(row.values())
    
    output.seek(0)
    return output.getvalue()

def export_events_to_csv(events_data):
    """Export events to CSV format"""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Title', 'Date', 'Time', 'Location', 'Description', 'Event Type', 'RSVP Count'])
    
    # Write data
    for event in events_data.get('events', []):
        rsvp_count = len(event.get('rsvps', []))
        writer.writerow([
            event.get('title', ''),
            event.get('date', ''),
            event.get('time', ''),
            event.get('location', ''),
            event.get('description', ''),
            event.get('event_type', ''),
            rsvp_count
        ])
    
    output.seek(0)
    return output.getvalue()

# PDF Report Generation
def generate_pdf_report():
    """Generate a comprehensive PDF report of all AHOY data with startup growth analysis"""
    from io import BytesIO
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get all data
    events_data = load_events()
    newsletter_data = load_newsletter_data()
    artist_data = load_artist_submissions()
    visits = load_analytics_data(30)
    stats = analyze_data(visits)
    
    # Get all RSVPs
    all_rsvps = []
    for event in events_data['events']:
        if 'rsvps' in event:
            for rsvp in event['rsvps']:
                clean_rsvp = {
                    "name": rsvp.get('name', ''),
                    "email": rsvp.get('email', ''),
                    "guest_count": rsvp.get('guest_count', 0),
                    "rsvp_date": rsvp.get('rsvp_date', ''),
                    "event_title": event['title'],
                    "event_date": event['date']
                }
                all_rsvps.append(clean_rsvp)
    
    # Build the story
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#f4c430')
    )
    story.append(Paragraph("AHOY Indie Media - Community Report", title_style))
    story.append(Paragraph("Events, Artists & Community Overview", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    # Report info
    info_style = ParagraphStyle(
        'ReportInfo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", info_style))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    summary_data = [
        ['Metric', 'Count'],
        ['Total Events', str(len(events_data.get('events', [])))],
        ['Newsletter Subscribers', str(len(newsletter_data.get('subscribers', [])))],
        ['Artist Submissions', str(len(artist_data.get('submissions', [])))],
        ['Total RSVPs', str(len(all_rsvps))],
        ['Website Visits (30 days)', str(stats.get('total_visits', 0))],
        ['Unique Visitors (30 days)', str(stats.get('unique_visitors', 0))]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4c430')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(PageBreak())
    
    # Community Overview
    story.append(Paragraph("Community Overview", styles['Heading2']))
    
    # Calculate current metrics
    current_month = datetime.now().month
    current_year = datetime.now().year
    events_this_year = [e for e in events_data['events'] if datetime.fromisoformat(e['date'].replace('Z', '+00:00')).year == current_year]
    events_this_month = [e for e in events_data['events'] if datetime.fromisoformat(e['date'].replace('Z', '+00:00')).month == current_month]
    
    story.append(Paragraph(f"<b>Events This Year:</b> {len(events_this_year)}", styles['Normal']))
    story.append(Paragraph(f"<b>Events This Month:</b> {len(events_this_month)}", styles['Normal']))
    story.append(Paragraph(f"<b>Newsletter Subscribers:</b> {len(newsletter_data.get('subscribers', []))}", styles['Normal']))
    story.append(Paragraph(f"<b>Artist Submissions:</b> {len(artist_data.get('submissions', []))}", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Event Attendance Analysis
    story.append(Paragraph("Event Attendance Analysis", styles['Heading2']))
    story.append(Paragraph("Event Performance Overview", styles['Heading3']))
    
    # Event financial analysis
    if events_data.get('events'):
        # Create events attendance table
        events_financial = [['Event Title', 'Date', 'Type', 'RSVPs', 'Total Guests', 'Event Status']]
        
        for event in events_data['events']:
            # Get RSVPs for this event
            event_rsvps = event.get('rsvps', [])
            rsvp_count = len(event_rsvps)
            
            # Calculate total guests (including guest counts)
            total_guests = sum(rsvp.get('guest_count', 1) for rsvp in event_rsvps)
            
            # Determine if event is past or upcoming
            is_past = datetime.fromisoformat(event['date'].replace('Z', '+00:00')) < datetime.now()
            event_status = "Completed" if is_past else "Upcoming"
            
            events_financial.append([
                event.get('title', 'N/A'),
                event.get('date', 'N/A')[:10],  # Just date part
                event.get('event_type', 'N/A'),
                str(rsvp_count),
                str(total_guests),
                event_status
            ])
        
        events_table = Table(events_financial, colWidths=[2*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
        events_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4c430')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        story.append(events_table)
        
        # Attendance summary
        total_guests_all_events = sum(
            sum(rsvp.get('guest_count', 1) for rsvp in event.get('rsvps', []))
            for event in events_data['events']
        )
        
        completed_events = [e for e in events_data['events'] if datetime.fromisoformat(e['date'].replace('Z', '+00:00')) < datetime.now()]
        upcoming_events = [e for e in events_data['events'] if datetime.fromisoformat(e['date'].replace('Z', '+00:00')) >= datetime.now()]
        
        story.append(Spacer(1, 20))
        story.append(Paragraph("Attendance Summary:", styles['Heading3']))
        story.append(Paragraph(f"<b>Total Events:</b> {len(events_data['events'])}", styles['Normal']))
        story.append(Paragraph(f"<b>Completed Events:</b> {len(completed_events)}", styles['Normal']))
        story.append(Paragraph(f"<b>Upcoming Events:</b> {len(upcoming_events)}", styles['Normal']))
        story.append(Paragraph(f"<b>Total Guests Across All Events:</b> {total_guests_all_events}", styles['Normal']))
        story.append(Paragraph(f"<b>Average Guests per Event:</b> {total_guests_all_events / max(len(events_data['events']), 1):.1f}", styles['Normal']))
    
    story.append(PageBreak())
    
    # Community Insights
    story.append(Paragraph("Community Insights", styles['Heading2']))
    
    insights = [
        "Our events bring together diverse artists and audiences in New Haven",
        "The community continues to grow with each event we host",
        "Artist submissions show the creative energy in our local arts scene",
        "Newsletter subscribers stay engaged with our event updates",
        "RSVPs help us plan better events and manage capacity"
    ]
    
    for insight in insights:
        story.append(Paragraph(f"• {insight}", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Looking Ahead
    story.append(Paragraph("Looking Ahead", styles['Heading2']))
    
    future_plans = [
        "Continue hosting regular events for our growing community",
        "Support local artists by providing performance opportunities",
        "Build connections between artists and audiences",
        "Create memorable experiences that celebrate New Haven's creative scene"
    ]
    
    for plan in future_plans:
        story.append(Paragraph(f"• {plan}", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Admin Authentication
def require_admin_auth(f):
    """Decorator to require admin authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def load_events():
    """Load events from JSON file"""
    try:
        with open('data/events.json', 'r') as f:
            events_data = json.load(f)
            # Add default image to events that don't have one
            for event in events_data.get('events', []):
                if 'image' not in event or not event['image']:
                    event['image'] = get_default_event_image(event['event_type'])
            return events_data
    except FileNotFoundError:
        return {"events": []}

def load_newsletter_data():
    """Load newsletter signups from JSON file"""
    try:
        with open('data/newsletter.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"subscribers": []}

def load_videos():
    """Load videos from JSON file"""
    try:
        with open('data/videos.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"videos": []}

def save_newsletter_data(newsletter_data):
    """Save newsletter signups to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open('data/newsletter.json', 'w') as f:
        json.dump(newsletter_data, f, indent=2, cls=DateEncoder)

def load_artist_submissions():
    """Load artist submissions from JSON file"""
    try:
        with open('data/artist_submissions.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"submissions": []}

def save_artist_submissions(artist_data):
    """Save artist submissions to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open('data/artist_submissions.json', 'w') as f:
        json.dump(artist_data, f, indent=2, cls=DateEncoder)

def save_events(events_data):
    """Save events to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open('data/events.json', 'w') as f:
        json.dump(events_data, f, indent=2, cls=DateEncoder)

def get_default_event_image(event_type):
    """Get default image path based on event type"""
    import random
    # Use real event photos from the event-imgs folder
    image_map = {
        'poetry': '/static/event-imgs/cabaret-1-2/1.jpg',
        'music': '/static/event-imgs/cabaret-1-2/2.jpg',
        'cabaret': '/static/event-imgs/cabaret-1-2/3.jpg',
        'default': '/static/event-imgs/cabaret-1-2/4.jpg'
    }
    return image_map.get(event_type, image_map['default'])

def get_upcoming_events():
    """Filter upcoming events"""
    events = load_events()['events']
    today = datetime.now().date()
    upcoming = [e for e in events if datetime.fromisoformat(e['date']).date() >= today]
    return sorted(upcoming, key=lambda x: x['date'])

def get_past_events():
    """Filter past events"""
    events = load_events()['events']
    today = datetime.now().date()
    past = [e for e in events if datetime.fromisoformat(e['date']).date() < today]
    return sorted(past, key=lambda x: x['date'], reverse=True)

def get_gallery_images():
    """Get all gallery images from event-imgs folders - community-sent first, then poetry, then cabaret"""
    import os
    import glob
    
    gallery_images = []
    
    # Get images from community-sent folder FIRST (top priority)
    community_path = 'static/event-imgs/community-sent'
    if os.path.exists(community_path):
        image_files = glob.glob(os.path.join(community_path, '*.jpg'))
        image_files.sort(key=lambda x: int(os.path.basename(x).split('.')[0]))
        
        for img_path in image_files:
            filename = os.path.basename(img_path)
            gallery_images.append({
                'src': f'/static/event-imgs/community-sent/{filename}',
                'alt': f'Community Photo {filename.split(".")[0]}',
                'thumbnail': f'/static/event-imgs/community-sent/{filename}'
            })
    
    # Get images from poets1 folder SECOND
    poets_path = 'static/event-imgs/poets1'
    if os.path.exists(poets_path):
        image_files = glob.glob(os.path.join(poets_path, '*.jpg'))
        image_files.sort(key=lambda x: int(os.path.basename(x).split('.')[0]))
        
        for img_path in image_files:
            filename = os.path.basename(img_path)
            gallery_images.append({
                'src': f'/static/event-imgs/poets1/{filename}',
                'alt': f'Poets and Friends Photo {filename.split(".")[0]}',
                'thumbnail': f'/static/event-imgs/poets1/{filename}'
            })
    
    # Get images from cabaret-1-2 folder THIRD
    cabaret_path = 'static/event-imgs/cabaret-1-2'
    if os.path.exists(cabaret_path):
        image_files = glob.glob(os.path.join(cabaret_path, '*.jpg'))
        image_files.sort(key=lambda x: int(os.path.basename(x).split('.')[0]))
        
        for img_path in image_files:
            filename = os.path.basename(img_path)
            gallery_images.append({
                'src': f'/static/event-imgs/cabaret-1-2/{filename}',
                'alt': f'Cabaret Event Photo {filename.split(".")[0]}',
                'thumbnail': f'/static/event-imgs/cabaret-1-2/{filename}'
            })
    
    return gallery_images

def find_available_port(start_port=5000, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port starting from {start_port}")

# Before request handler for analytics
@app.before_request
def before_request():
    """Track every request"""
    # Skip tracking for static files and admin analytics
    if (request.endpoint and 
        not request.endpoint.startswith('static') and 
        request.path != '/admin/analytics' and
        request.path != '/admin/login'):
        track_visit(request)

# Admin Authentication Routes
@app.route('/admin/login', methods=['GET', 'POST'])
@csrf.exempt
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        try:
            password = request.form.get('password', '')
            if password == 'eeeELLENsoCUTE':
                session['admin_logged_in'] = True
                flash('Successfully logged in!', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Invalid password!', 'error')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login error. Please try again.', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# Routes
@app.route('/')
def home():
    latest_events = get_upcoming_events()[:3]  # Show next 3 events
    recent_past_events = get_past_events()[:3]  # Show 3 most recent past events
    return render_template('index.html', latest_events=latest_events, recent_past_events=recent_past_events)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/events')
def events():
    upcoming = get_upcoming_events()
    past = get_past_events()
    
    # Get all gallery images
    gallery_images = get_gallery_images()
    print(f"DEBUG: Found {len(gallery_images)} gallery images")
    
    # Get video data
    videos_data = load_videos()
    videos = videos_data.get('videos', [])
    
    # Create a mapping of event_id to video for easy lookup
    video_map = {video['event_id']: video for video in videos if video.get('event_id')}
    
    return render_template('events.html', upcoming=upcoming, past=past, gallery_images=gallery_images, video_map=video_map)

@app.route('/download')
def download():
    return render_template('download.html')

@app.route('/artist-submission')
def artist_submission_page():
    return render_template('artist_submission.html')

@app.route('/service-policy')
def service_policy():
    current_date = datetime.now().strftime('%B %d, %Y')
    return render_template('service_policy.html', current_date=current_date)

@app.route('/privacy-policy')
def privacy_policy():
    current_date = datetime.now().strftime('%B %d, %Y')
    return render_template('privacy_policy.html', current_date=current_date)


@app.route('/admin')
@require_admin_auth
def admin():
    events = load_events()['events']
    newsletter_data = load_newsletter_data()
    artist_data = load_artist_submissions()
    
    # Get all RSVPs from all events
    all_rsvps = []
    for event in events:
        if event.get('rsvps'):
            for rsvp in event['rsvps']:
                rsvp['event_title'] = event['title']
                rsvp['event_date'] = event['date']
                all_rsvps.append(rsvp)
    
    # Sort RSVPs by date (newest first)
    all_rsvps.sort(key=lambda x: x['rsvp_date'], reverse=True)
    
    # Sort artist submissions by date (newest first)
    artist_submissions = sorted(artist_data['submissions'], key=lambda x: x['submission_date'], reverse=True)
    
    return render_template('admin.html', 
                         events=events, 
                         subscribers=newsletter_data['subscribers'],
                         all_rsvps=all_rsvps,
                         artist_submissions=artist_submissions)

@app.route('/admin/analytics')
@require_admin_auth
def analytics_dashboard():
    """Analytics dashboard for admins"""
    days = request.args.get('days', 7, type=int)
    visits = load_analytics_data(days)
    stats = analyze_data(visits)
    
    return render_template('analytics.html', 
                         stats=stats, 
                         days=days,
                         raw_visits=visits[-50:])  # Last 50 visits for recent activity

@app.route('/admin/analytics/export')
@require_admin_auth
def export_analytics():
    """Export analytics data as human-readable JSON"""
    days = request.args.get('days', 30, type=int)
    visits = load_analytics_data(days)
    stats = analyze_data(visits)
    
    # Format for better readability
    formatted_data = {
        "export_info": {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_period_days": days,
            "data_type": "Website Analytics"
        },
        "summary_statistics": stats,
        "raw_visit_data": visits[-100:]  # Last 100 visits for detailed analysis
    }
    
    response = app.response_class(
        response=json.dumps(formatted_data, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=ahoy_analytics_{datetime.now().strftime("%Y%m%d")}.json'
    return response

@app.route('/admin/export/newsletter')
@require_admin_auth
def export_newsletter():
    """Export newsletter subscribers in various formats"""
    format_type = request.args.get('format', 'json')
    newsletter_data = load_newsletter_data()
    subscribers = newsletter_data.get('subscribers', [])
    
    if format_type == 'csv':
        csv_data = export_to_csv(subscribers, 'newsletter_subscribers')
        response = app.response_class(
            response=csv_data,
            status=200,
            mimetype='text/csv'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=ahoy_newsletter_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    else:  # JSON format
        formatted_data = {
            "export_info": {
                "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_subscribers": len(subscribers),
                "data_type": "Newsletter Subscribers"
            },
            "subscribers": subscribers
        }
        
        response = app.response_class(
            response=json.dumps(formatted_data, indent=2),
            status=200,
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=ahoy_newsletter_{datetime.now().strftime("%Y%m%d")}.json'
        return response

@app.route('/admin/export/artist-submissions')
@require_admin_auth
def export_artist_submissions():
    """Export artist submissions in various formats"""
    format_type = request.args.get('format', 'json')
    artist_data = load_artist_submissions()
    submissions = artist_data.get('submissions', [])
    
    if format_type == 'csv':
        csv_data = export_to_csv(submissions, 'artist_submissions')
        response = app.response_class(
            response=csv_data,
            status=200,
            mimetype='text/csv'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=ahoy_artist_submissions_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    else:  # JSON format
        formatted_data = {
            "export_info": {
                "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_submissions": len(submissions),
                "data_type": "Artist Performance Submissions"
            },
            "submissions": submissions
        }
        
        response = app.response_class(
            response=json.dumps(formatted_data, indent=2),
            status=200,
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=ahoy_artist_submissions_{datetime.now().strftime("%Y%m%d")}.json'
        return response

@app.route('/admin/export/rsvps')
@require_admin_auth
def export_rsvps():
    """Export all RSVPs as human-readable JSON"""
    events = load_events()['events']
    all_rsvps = []
    
    for event in events:
        if 'rsvps' in event:
            for rsvp in event['rsvps']:
                # Create a clean RSVP object with event info
                clean_rsvp = {
                    "rsvp_id": rsvp.get('id', ''),
                    "name": rsvp.get('name', ''),
                    "email": rsvp.get('email', ''),
                    "guest_count": rsvp.get('guest_count', 0),
                    "rsvp_date": rsvp.get('rsvp_date', ''),
                    "event_info": {
                        "event_title": event['title'],
                        "event_date": event['date'],
                        "event_time": event.get('time', ''),
                        "event_location": event.get('location', '')
                    }
                }
                all_rsvps.append(clean_rsvp)
    
    all_rsvps.sort(key=lambda x: x['rsvp_date'], reverse=True)
    
    # Format for better readability
    formatted_data = {
        "export_info": {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_rsvps": len(all_rsvps),
            "data_type": "Event RSVPs"
        },
        "rsvps": all_rsvps
    }
    
    response = app.response_class(
        response=json.dumps(formatted_data, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=ahoy_rsvps_{datetime.now().strftime("%Y%m%d")}.json'
    return response

@app.route('/admin/export/all-data')
@require_admin_auth
def export_all_data():
    """Export all data as human-readable JSON"""
    events_data = load_events()
    newsletter_data = load_newsletter_data()
    artist_data = load_artist_submissions()
    
    # Get all RSVPs with clean formatting
    all_rsvps = []
    for event in events_data['events']:
        if 'rsvps' in event:
            for rsvp in event['rsvps']:
                clean_rsvp = {
                    "rsvp_id": rsvp.get('id', ''),
                    "name": rsvp.get('name', ''),
                    "email": rsvp.get('email', ''),
                    "guest_count": rsvp.get('guest_count', 0),
                    "rsvp_date": rsvp.get('rsvp_date', ''),
                    "event_info": {
                        "event_title": event['title'],
                        "event_date": event['date'],
                        "event_time": event.get('time', ''),
                        "event_location": event.get('location', '')
                    }
                }
                all_rsvps.append(clean_rsvp)
    
    # Format all data for better readability
    all_data = {
        "export_info": {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_type": "Complete AHOY Data Export",
            "summary": {
                "total_events": len(events_data.get('events', [])),
                "total_newsletter_subscribers": len(newsletter_data.get('subscribers', [])),
                "total_artist_submissions": len(artist_data.get('submissions', [])),
                "total_rsvps": len(all_rsvps)
            }
        },
        "events": events_data,
        "newsletter_subscribers": newsletter_data,
        "artist_submissions": artist_data,
        "rsvps": all_rsvps
    }
    
    response = app.response_class(
        response=json.dumps(all_data, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=ahoy_all_data_{datetime.now().strftime("%Y%m%d")}.json'
    return response

@app.route('/admin/export/pdf-report')
@require_admin_auth
def export_pdf_report():
    """Export comprehensive report in various formats"""
    format_type = request.args.get('format', 'pdf')
    
    if format_type == 'pdf':
        try:
            pdf_buffer = generate_pdf_report()
            
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=ahoy_community_report_{datetime.now().strftime("%Y%m%d")}.pdf'
            
            return response
        except Exception as e:
            flash(f'Error generating PDF report: {str(e)}', 'error')
            return redirect(url_for('admin'))
    else:
        # For JSON format, return a simplified report
        try:
            events_data = load_events()
            newsletter_data = load_newsletter_data()
            artist_data = load_artist_submissions()
            visits = load_analytics_data(30)
            stats = analyze_data(visits)
            
            # Get all RSVPs
            all_rsvps = []
            for event in events_data['events']:
                if 'rsvps' in event:
                    for rsvp in event['rsvps']:
                        clean_rsvp = {
                            "name": rsvp.get('name', ''),
                            "email": rsvp.get('email', ''),
                            "guest_count": rsvp.get('guest_count', 0),
                            "rsvp_date": rsvp.get('rsvp_date', ''),
                            "event_title": event['title'],
                            "event_date": event['date']
                        }
                        all_rsvps.append(clean_rsvp)
            
            report_data = {
                "export_info": {
                    "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "report_type": "Community Report",
                    "format": "json"
                },
                "summary": {
                    "total_events": len(events_data.get('events', [])),
                    "newsletter_subscribers": len(newsletter_data.get('subscribers', [])),
                    "artist_submissions": len(artist_data.get('submissions', [])),
                    "total_rsvps": len(all_rsvps),
                    "website_visits_30_days": stats.get('total_visits', 0),
                    "unique_visitors_30_days": stats.get('unique_visitors', 0)
                },
                "events": events_data.get('events', []),
                "newsletter_subscribers": newsletter_data.get('subscribers', []),
                "artist_submissions": artist_data.get('submissions', []),
                "rsvps": all_rsvps,
                "analytics": stats
            }
            
            response = app.response_class(
                response=json.dumps(report_data, indent=2),
                status=200,
                mimetype='application/json'
            )
            response.headers['Content-Disposition'] = f'attachment; filename=ahoy_community_report_{datetime.now().strftime("%Y%m%d")}.json'
            return response
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return redirect(url_for('admin'))

@app.route('/admin/event/new', methods=['GET', 'POST'])
@csrf.exempt
def new_event():
    if request.method == 'POST':
        event_data = {
            'id': datetime.now().isoformat(),
            'title': request.form['title'],
            'date': request.form['date'],
            'time': request.form.get('time', ''),
            'venue': request.form.get('venue', ''),
            'venue_address': request.form.get('venue_address', ''),
            'event_type': request.form.get('event_type', 'cabaret'),
            'status': request.form.get('status', 'upcoming'),
            'description': request.form.get('description', ''),
            'image': request.form.get('image', get_default_event_image(request.form.get('event_type', 'cabaret'))),
            'photos': [],
            'rsvp_enabled': request.form.get('rsvp_enabled', 'false') == 'true',
            'rsvp_limit': request.form.get('rsvp_limit', ''),
            'rsvps': []
        }
        
        events = load_events()
        events['events'].append(event_data)
        save_events(events)
        
        flash('Event added successfully!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('event_form.html', event=None)

@app.route('/admin/event/edit/<event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    events = load_events()
    event = next((e for e in events['events'] if e['id'] == event_id), None)
    
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        event.update({
            'title': request.form['title'],
            'date': request.form['date'],
            'time': request.form.get('time', ''),
            'venue': request.form.get('venue', ''),
            'venue_address': request.form.get('venue_address', ''),
            'event_type': request.form.get('event_type', 'cabaret'),
            'status': request.form.get('status', 'upcoming'),
            'description': request.form.get('description', ''),
            'image': request.form.get('image', get_default_event_image(request.form.get('event_type', 'cabaret'))),
            'rsvp_enabled': request.form.get('rsvp_enabled', 'false') == 'true',
            'rsvp_limit': request.form.get('rsvp_limit', '')
        })
        
        save_events(events)
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('event_form.html', event=event)

@app.route('/admin/event/delete/<event_id>', methods=['POST'])
def delete_event(event_id):
    events = load_events()
    events['events'] = [e for e in events['events'] if e['id'] != event_id]
    save_events(events)
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/newsletter', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limiting
def newsletter_signup():
    email = request.form.get('email', '').strip()
    
    # Enhanced validation
    if not email:
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    # Validate email format
    if not validate_email(email):
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    # Sanitize email
    email = sanitize_input(email, 254)
    
    # Check for suspicious content
    if is_suspicious_content(email):
        flash('Invalid email format.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    # Load existing newsletter data
    newsletter_data = load_newsletter_data()
    
    # Check if email already exists
    existing_subscriber = next((s for s in newsletter_data['subscribers'] if s['email'] == email), None)
    if existing_subscriber:
        flash('This email is already subscribed to our newsletter!', 'info')
    else:
        # Collect only essential business data
        now = datetime.now()
        user_agent = request.headers.get('User-Agent', '')
        referrer = request.referrer or ''
        ip_address = request.remote_addr
        
        # Simple device type detection
        device_type = "Desktop"
        if user_agent:
            if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent:
                device_type = "Mobile"
            elif "Tablet" in user_agent or "iPad" in user_agent:
                device_type = "Tablet"
        
        # Extract domain from referrer
        referrer_domain = ""
        if referrer:
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(referrer)
                referrer_domain = parsed_url.netloc
            except:
                referrer_domain = referrer[:100]
        
        # Generate human-readable ID
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        email_prefix = email.split('@')[0][:8] if '@' in email else 'user'
        human_id = f"sub_{timestamp_str}_{email_prefix}"
        
        # Basic geographic data from IP (simplified)
        region = "Unknown"
        country = "Unknown"
        if ip_address:
            # Simple IP-based region detection (you could integrate with a real service)
            if ip_address.startswith('127.') or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
                region = "Local"
                country = "Local"
            elif ip_address.startswith('172.'):
                region = "Local"
                country = "Local"
            else:
                # For demo purposes - in production, use a real geolocation service
                region = "North America"  # Default assumption
                country = "US"  # Default assumption
        
        # Add new subscriber with essential business data (enhanced with regional info)
        subscriber = {
            'id': human_id,
            'email': email,
            'signup_date': now.strftime("%Y-%m-%d %H:%M:%S"),
            'signup_timestamp': now.timestamp(),
            'status': 'active',
            'device_type': device_type,
            'referrer_domain': referrer_domain,
            'campaign_source': request.args.get('utm_source', ''),
            'campaign_medium': request.args.get('utm_medium', ''),
            'email_domain': email.split('@')[1] if '@' in email else '',
            'is_mobile': device_type == "Mobile",
            'region': region,
            'country': country,
            'signup_hour': now.hour,
            'signup_weekday': now.strftime('%A'),
            'timezone': 'EST'  # Could be detected from IP in production
        }
        
        newsletter_data['subscribers'].append(subscriber)
        save_newsletter_data(newsletter_data)
        flash('Thanks for subscribing to our newsletter!', 'success')
    
    # Redirect back to the previous page
    return redirect(request.referrer or url_for('home'))

@app.route('/artist-submission', methods=['POST'])
@limiter.limit("3 per hour")  # Rate limiting for artist submissions
def artist_submission():
    # Get and sanitize form data
    name = sanitize_input(request.form.get('name', ''), 100)
    email = request.form.get('email', '').strip()
    performance_type = sanitize_input(request.form.get('performance_type', ''), 50)
    description = sanitize_input(request.form.get('description', ''), 2000)
    availability = sanitize_input(request.form.get('availability', ''), 500)
    links = request.form.get('links', '').strip()
    
    # Validate required fields
    if not name or not email or not performance_type or not description:
        flash('Please fill in all required fields.', 'error')
        return redirect(request.referrer or url_for('artist_submission_page'))
    
    # Enhanced email validation
    if not validate_email(email):
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer or url_for('artist_submission_page'))
    
    # Sanitize email
    email = sanitize_input(email, 254)
    
    # Validate performance type (whitelist approach)
    valid_performance_types = ['music', 'poetry', 'cabaret', 'comedy', 'dance', 'theater', 'other']
    if performance_type not in valid_performance_types:
        flash('Please select a valid performance type.', 'error')
        return redirect(request.referrer or url_for('artist_submission_page'))
    
    # Validate URL if provided
    if links and not validate_url(links):
        flash('Please enter a valid URL for your links.', 'error')
        return redirect(request.referrer or url_for('artist_submission_page'))
    
    # Sanitize URL
    links = sanitize_input(links, 500)
    
    # Check for suspicious content
    suspicious_fields = [name, description, availability]
    for field in suspicious_fields:
        if is_suspicious_content(field):
            flash('Your submission contains content that appears to be spam. Please review and resubmit.', 'error')
            return redirect(request.referrer or url_for('artist_submission_page'))
    
    # Load existing artist submissions
    artist_data = load_artist_submissions()
    
    # Check if email already exists
    existing_submission = next((s for s in artist_data['submissions'] if s['email'] == email), None)
    if existing_submission:
        flash('We already have a submission from this email address. We\'ll be in touch soon!', 'info')
    else:
        # Add new artist submission
        submission = {
            'id': datetime.now().isoformat(),
            'name': name,
            'email': email,
            'performance_type': performance_type,
            'description': description,
            'availability': availability,
            'links': links,
            'submission_date': datetime.now().isoformat(),
            'status': 'pending',
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:200]
        }
        artist_data['submissions'].append(submission)
        save_artist_submissions(artist_data)
        flash('Thanks for your submission! We\'ll review it and get back to you soon.', 'success')
    
    # Redirect back to the artist submission page
    return redirect(url_for('artist_submission_page'))

@app.route('/rsvp/<event_id>', methods=['POST'])
def rsvp_event(event_id):
    events = load_events()
    event = next((e for e in events['events'] if e['id'] == event_id), None)
    
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'}), 404
    
    if not event.get('rsvp_enabled', False):
        return jsonify({'success': False, 'message': 'RSVP not enabled for this event'}), 400
    
    # Check if RSVP limit is reached
    rsvp_limit = event.get('rsvp_limit')
    if rsvp_limit and len(event.get('rsvps', [])) >= int(rsvp_limit):
        return jsonify({'success': False, 'message': 'Event is full'}), 400
    
    # Get RSVP data
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    guests = int(request.form.get('guests', 1))
    
    if not name or not email:
        return jsonify({'success': False, 'message': 'Name and email are required'}), 400
    
    # Check if email already RSVP'd
    existing_rsvp = next((r for r in event.get('rsvps', []) if r['email'] == email), None)
    if existing_rsvp:
        return jsonify({'success': False, 'message': 'You have already RSVP\'d for this event'}), 400
    
    # Add RSVP
    rsvp_data = {
        'id': datetime.now().isoformat(),
        'name': name,
        'email': email,
        'guests': guests,
        'rsvp_date': datetime.now().isoformat()
    }
    
    if 'rsvps' not in event:
        event['rsvps'] = []
    event['rsvps'].append(rsvp_data)
    
    save_events(events)
    
    return jsonify({
        'success': True, 
        'message': f'Successfully RSVP\'d for {event["title"]}!',
        'rsvp_count': len(event['rsvps'])
    })

@app.route('/rsvp/<event_id>/cancel', methods=['POST'])
def cancel_rsvp(event_id):
    events = load_events()
    event = next((e for e in events['events'] if e['id'] == event_id), None)
    
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'}), 404
    
    email = request.form.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    
    # Remove RSVP
    event['rsvps'] = [r for r in event.get('rsvps', []) if r['email'] != email]
    
    save_events(events)
    
    return jsonify({
        'success': True, 
        'message': 'RSVP cancelled successfully',
        'rsvp_count': len(event['rsvps'])
    })

if __name__ == '__main__':
    import os
    # Try to use the PORT environment variable first, then find an available port
    try:
        port = int(os.environ.get('PORT', 5000))
        # Test if the port is available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
    except (ValueError, OSError):
        # If PORT env var is invalid or port is in use, find an available port
        port = find_available_port()
        print(f"Port 5000 is in use. Using port {port} instead.")
    
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

# SEO Routes
@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

# Data export routes
