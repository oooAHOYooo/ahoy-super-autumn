from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import json
import os
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
            return json.load(f)
    except FileNotFoundError:
        return {"events": []}

def save_events(events_data):
    """Save events to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open('data/events.json', 'w') as f:
        json.dump(events_data, f, indent=2, cls=DateEncoder)

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
            'description': request.form.get('description', ''),
            'type': request.form.get('type', 'show')
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
            'description': request.form.get('description', ''),
            'type': request.form.get('type', 'show')
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

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
