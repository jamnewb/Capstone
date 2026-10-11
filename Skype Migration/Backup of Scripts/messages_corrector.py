import json

# Load the JSON file
with open('messages.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Reverse the MessageList in each conversation
for convo in data['conversations']:
    convo['MessageList'].reverse()

# (Optional) Save the reversed version if needed
with open('messages_reversed.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
