from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
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
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == 'eeeELLENsoCUTE':
            session['admin_logged_in'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid password!', 'error')
    
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
    return render_template('index.html', latest_events=latest_events)

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
    
    return render_template('events.html', upcoming=upcoming, past=past, gallery_images=gallery_images)

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
    """Export analytics data as JSON"""
    days = request.args.get('days', 30, type=int)
    visits = load_analytics_data(days)
    stats = analyze_data(visits)
    
    response = app.response_class(
        response=json.dumps({
            'stats': stats,
            'visits': visits
        }, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=ahoy_analytics_{datetime.now().strftime("%Y%m%d")}.json'
    return response

@app.route('/admin/event/new', methods=['GET', 'POST'])
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
@app.route('/admin/export/newsletter')
def export_newsletter():
    """Export newsletter subscribers as JSON"""
    newsletter_data = load_newsletter_data()
    return jsonify(newsletter_data)

@app.route('/admin/export/artist-submissions')
def export_artist_submissions():
    """Export artist submissions as JSON"""
    artist_data = load_artist_submissions()
    return jsonify(artist_data)

@app.route('/admin/export/rsvps')
def export_rsvps():
    """Export all RSVPs as JSON"""
    events = load_events()['events']
    all_rsvps = []
    for event in events:
        if event.get('rsvps'):
            for rsvp in event['rsvps']:
                rsvp['event_title'] = event['title']
                rsvp['event_date'] = event['date']
                all_rsvps.append(rsvp)
    
    return jsonify({"rsvps": all_rsvps})

@app.route('/admin/export/all')
def export_all_data():
    """Export all data (events, newsletter, artist submissions, RSVPs) as JSON"""
    events_data = load_events()
    newsletter_data = load_newsletter_data()
    artist_data = load_artist_submissions()
    
    # Get all RSVPs
    all_rsvps = []
    for event in events_data['events']:
        if event.get('rsvps'):
            for rsvp in event['rsvps']:
                rsvp['event_title'] = event['title']
                rsvp['event_date'] = event['date']
                all_rsvps.append(rsvp)
    
    return jsonify({
        "events": events_data['events'],
        "newsletter_subscribers": newsletter_data['subscribers'],
        "artist_submissions": artist_data['submissions'],
        "rsvps": all_rsvps,
        "export_date": datetime.now().isoformat()
    })
