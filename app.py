from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import json
import os
import socket
from datetime import datetime, date
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

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

def save_events(events_data):
    """Save events to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open('data/events.json', 'w') as f:
        json.dump(events_data, f, indent=2, cls=DateEncoder)

def get_default_event_image(event_type):
    """Get default image path based on event type"""
    # For now, use the same image for all events
    # Later this can be expanded to have different images per event type
    return '/static/uploads/devPhoto_poets3.jpg'

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
    return render_template('events.html', upcoming=upcoming, past=past)

@app.route('/download')
def download():
    return render_template('download.html')

@app.route('/service-policy')
def service_policy():
    current_date = datetime.now().strftime('%B %d, %Y')
    return render_template('service_policy.html', current_date=current_date)

@app.route('/privacy-policy')
def privacy_policy():
    current_date = datetime.now().strftime('%B %d, %Y')
    return render_template('privacy_policy.html', current_date=current_date)

@app.route('/admin')
def admin():
    events = load_events()['events']
    return render_template('admin.html', events=events)

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
def newsletter_signup():
    email = request.form.get('email')
    if email:
        # For now, just show a success message
        # In a real app, you'd save this to a database
        flash('Thanks for subscribing to our newsletter!', 'success')
    else:
        flash('Please enter a valid email address.', 'error')
    
    # Redirect back to the previous page
    return redirect(request.referrer or url_for('home'))

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
