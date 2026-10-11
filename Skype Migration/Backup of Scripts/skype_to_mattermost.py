import json
import os
import requests
import re
import time
from datetime import datetime

# Load Skype messages
with open('messages_reversed.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Mattermost API Setup
mattermost_post_url = 'http://localhost:8065/api/v4/posts'
mattermost_file_url = 'http://localhost:8065/api/v4/files'
mattermost_channel_url = 'http://localhost:8065/api/v4/channels'
auth_token = 'ghamphdmk3bpbbwnwt6x8t7kno'  # Your token
team_id = '1s3j5b8udt8zxfzy7djeentw6a'  # ❗Insert your Mattermost team ID here

headers = {
    'Authorization': f'Bearer {auth_token}',
}

media_folder = r'C:\Users\James\Desktop\Skype Migration\Scripts\media'

# Channel ID for "Migration Documentation" where updates will be posted
migration_channel_id = "7hbzag8117f69n6mhpqg3b1rco"  # Use your channel ID

# Helper to create a Mattermost channel
def create_channel(name, display_name):
    safe_name = re.sub(r'[^a-z0-9\-]', '-', name.lower())  # Mattermost channel names must be lowercase and hyphenated
    payload = {
        "team_id": team_id,
        "name": safe_name,
        "display_name": display_name,
        "type": "P"  # "P" = private channel; use "O" for public
    }
    response = requests.post(mattermost_channel_url, headers={**headers, 'Content-Type': 'application/json'}, json=payload)
    if response.status_code == 201:
        return response.json()['id']
    elif response.status_code == 400 and "A channel with that name already exists" in response.text:
        print(f"⚠️ Channel '{safe_name}' already exists. Please delete manually or handle in script.")
        return None
    else:
        print(f"❌ Failed to create channel: {response.status_code} {response.text}")
        return None

# Map user IDs to display names dynamically
def get_user_display_name(user_id, msg):
    display_name = msg.get('displayName', None)
    
    if display_name:
        return display_name
    else:
        return user_id

# Function to post the migration update to "Migration Documentation" channel
def post_migration_update(conversation_name, num_members, num_messages):
    message = f"The conversation '{conversation_name}' has been migrated. ({num_members} members, {num_messages} messages)."
    payload = {
        'channel_id': migration_channel_id,
        'message': message
    }
    response = requests.post(mattermost_post_url, headers={**headers, 'Content-Type': 'application/json'}, json=payload)
    if response.status_code != 201:
        print(f"❌ Failed to post migration update: {response.status_code} {response.text}")

# Process each Skype conversation
for convo in data.get('conversations', []):
    topic = convo.get('threadProperties', {}).get('topic', 'skype-import')
    members = json.loads(convo.get('threadProperties', {}).get('members', '[]'))
    
    if isinstance(members, str):
        members = json.loads(members)  # Ensure members is a list if it's a string

    print(f"▶️ Processing Skype conversation with topic: {topic}")

    # Create Mattermost channel
    channel_id = create_channel(topic, topic)
    if not channel_id:
        print(f"Skipping conversation '{topic}' due to channel creation failure.")
        continue

    # Gather conversation messages
    conversation = []
    for msg in convo.get('MessageList', []):
        sender_id = msg.get('from')
        display_name = get_user_display_name(sender_id, msg)
        print("actual displayname gotten")
        print(display_name)

        # Only process messages from valid users
        if sender_id:
            conversation.append((msg, display_name))

    # Post each message
    for msg, sender in conversation:
        text = msg.get('content', '').strip()
        timestamp = msg.get('originalarrivaltime', '')
        if timestamp:
            try:
                # Parse the ISO 8601 timestamp using datetime.fromisoformat
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                print(f"❌ Failed to parse timestamp: {timestamp}")

        if msg.get('messagetype') == 'RichText':
            # Normal text message
            if text:
                payload = {
                    'channel_id': channel_id,
                    'message': f"[{timestamp}] {sender}: {text}"
                }
                response = requests.post(mattermost_post_url, headers={**headers, 'Content-Type': 'application/json'}, json=payload)
                if response.status_code != 201:
                    print(f"❌ Failed to send message: {response.status_code} {response.text}")

        elif msg.get('messagetype') == 'RichText/UriObject':
            # It's a media file
            match = re.search(r'doc_id="([^"]+)"', text)
            if match:
                doc_id = match.group(1)
                possible_files = [f for f in os.listdir(media_folder) if f.startswith(doc_id)]
                if possible_files:
                    filepath = os.path.join(media_folder, possible_files[0])
                    with open(filepath, 'rb') as f:
                        files = {'files': (os.path.basename(filepath), f)}
                        file_upload_payload = {
                            'channel_id': channel_id
                        }
                        upload_response = requests.post(mattermost_file_url, headers=headers, files=files, data=file_upload_payload)
                        if upload_response.status_code == 201:
                            file_id = upload_response.json()['file_infos'][0]['id']
                            post_payload = {
                                'channel_id': channel_id,
                                'message': f"[{timestamp}] {sender} uploaded a file:",
                                'file_ids': [file_id]
                            }
                            post_response = requests.post(mattermost_post_url, headers={**headers, 'Content-Type': 'application/json'}, json=post_payload)
                            if post_response.status_code != 201:
                                print(f"❌ Failed to post uploaded file message: {post_response.status_code} {post_response.text}")
                        else:
                            print(f"❌ Failed to upload file: {upload_response.status_code} {upload_response.text}")
                else:
                    print(f"⚠️ No local file found for doc_id {doc_id}")

        # Pause a bit to avoid API flooding
        time.sleep(0.2)

    # Post migration summary after each conversation
    post_migration_update(topic, len(members), len(conversation))

print("✅ Migration complete!")
