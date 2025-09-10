#!/usr/bin/env python3
"""
Data sync script for AHOY Indie Media
This script helps sync data from the live site to your local development environment.
"""

import requests
import json
import os
from datetime import datetime

# Configuration
LIVE_SITE_URL = "https://ahoynewhaven.org"
ADMIN_PASSWORD = "eeeELLENsoCUTE"  # Your admin password

def sync_newsletter_data():
    """Sync newsletter data from live site"""
    try:
        # First, login to get session
        session = requests.Session()
        
        # Login
        login_data = {"password": ADMIN_PASSWORD}
        login_response = session.post(f"{LIVE_SITE_URL}/admin/login", data=login_data)
        
        if login_response.status_code == 200:
            # Get newsletter data
            newsletter_response = session.get(f"{LIVE_SITE_URL}/admin/export/newsletter?format=json")
            
            if newsletter_response.status_code == 200:
                newsletter_data = newsletter_response.json()
                
                # Save to local file
                with open('data/newsletter.json', 'w') as f:
                    json.dump(newsletter_data, f, indent=2)
                
                print(f"✅ Synced {len(newsletter_data.get('subscribers', []))} newsletter subscribers")
                return True
            else:
                print(f"❌ Failed to get newsletter data: {newsletter_response.status_code}")
        else:
            print(f"❌ Failed to login: {login_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error syncing newsletter data: {e}")
    
    return False

def sync_artist_submissions():
    """Sync artist submissions from live site"""
    try:
        session = requests.Session()
        
        # Login
        login_data = {"password": ADMIN_PASSWORD}
        login_response = session.post(f"{LIVE_SITE_URL}/admin/login", data=login_data)
        
        if login_response.status_code == 200:
            # Get artist submissions
            artist_response = session.get(f"{LIVE_SITE_URL}/admin/export/artist-submissions?format=json")
            
            if artist_response.status_code == 200:
                artist_data = artist_response.json()
                
                # Save to local file
                with open('data/artist_submissions.json', 'w') as f:
                    json.dump(artist_data, f, indent=2)
                
                print(f"✅ Synced {len(artist_data.get('submissions', []))} artist submissions")
                return True
            else:
                print(f"❌ Failed to get artist data: {artist_response.status_code}")
        else:
            print(f"❌ Failed to login: {login_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error syncing artist data: {e}")
    
    return False

def sync_events_data():
    """Sync events data from live site"""
    try:
        session = requests.Session()
        
        # Login
        login_data = {"password": ADMIN_PASSWORD}
        login_response = session.post(f"{LIVE_SITE_URL}/admin/login", data=login_data)
        
        if login_response.status_code == 200:
            # Get all data (includes events)
            all_data_response = session.get(f"{LIVE_SITE_URL}/admin/export/all-data?format=json")
            
            if all_data_response.status_code == 200:
                all_data = all_data_response.json()
                
                # Save events data
                if 'events' in all_data:
                    with open('data/events.json', 'w') as f:
                        json.dump(all_data['events'], f, indent=2)
                    
                    print(f"✅ Synced {len(all_data['events'].get('events', []))} events")
                    return True
            else:
                print(f"❌ Failed to get events data: {all_data_response.status_code}")
        else:
            print(f"❌ Failed to login: {login_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error syncing events data: {e}")
    
    return False

def main():
    """Main sync function"""
    print("🔄 Syncing data from live site...")
    print(f"📡 Live site: {LIVE_SITE_URL}")
    print(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Sync all data
    newsletter_success = sync_newsletter_data()
    artist_success = sync_artist_submissions()
    events_success = sync_events_data()
    
    print("-" * 50)
    if newsletter_success and artist_success and events_success:
        print("🎉 All data synced successfully!")
    else:
        print("⚠️  Some data sync failed. Check the errors above.")

if __name__ == "__main__":
    main()
