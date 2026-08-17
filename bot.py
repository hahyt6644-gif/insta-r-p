import os
import json
import time
import requests
import telebot
import threading
from flask import Flask, request, redirect, render_template_string
from instagrapi import Client

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
BOT_TOKEN = "8155064317:AAH2O9sWOUW20n4HVKEov5ULE3cy3fDkJ0k"
ADMIN_CHAT_ID = "7284363064"
ACCOUNTS_FILE = "accounts.json"
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

os.makedirs("downloads", exist_ok=True)

# --- Helper Functions ---
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    with open(ACCOUNTS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==========================================
# 🤖 TELEGRAM BOT LOGIC
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        bot.reply_to(message, "🤖 Bot ready!\n\n📹 Send a video to upload.\n📸 /dp - Force-update profile pics.\n📦 /export - Download accounts backup.\n📥 /import - Reply to a JSON file to restore.")

@bot.message_handler(commands=['export'])
def export_data(message):
    """Sends the accounts.json file to the admin"""
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
        
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "rb") as f:
            bot.send_document(message.chat.id, f, caption="📦 Here is your accounts backup file!")
    else:
        bot.reply_to(message, "❌ No data found to export.")

@bot.message_handler(commands=['import'])
def import_data(message):
    """Imports accounts from a JSON file replied to by the admin"""
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
        
    # Check if the admin is replying to a file
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "❌ Please **reply** to a `.json` file with the command `/import`", parse_mode="Markdown")
        return
        
    doc = message.reply_to_message.document
    if not doc.file_name.endswith('.json'):
        bot.reply_to(message, "❌ Only `.json` files are supported!")
        return
        
    try:
        # Download the file from Telegram
        file_info = bot.get_file(doc.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Verify it's valid JSON
        new_data = json.loads(downloaded_file)
        
        # Save it
        save_accounts(new_data)
        bot.reply_to(message, f"✅ Successfully imported **{len(new_data)}** accounts!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to import JSON file:\n`{e}`", parse_mode="Markdown")

@bot.message_handler(commands=['dp'])
def update_dps(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    
    accounts = load_accounts()
    if not accounts:
        bot.reply_to(message, "❌ No accounts found in dashboard!")
        return

    bot.reply_to(message, "🔄 Fetching fresh Profile Pictures for all accounts...")
    
    for username, data in accounts.items():
        try:
            cl = Client()
            cl.login_by_sessionid(data["session_string"])
            user_info = cl.user_info(cl.user_id)
            
            dp_path = f"downloads/{username}_dp.jpg"
            with open(dp_path, "wb") as f:
                f.write(requests.get(user_info.profile_pic_url).content)
                
            bot.send_message(message.chat.id, f"✅ Updated DP for `{username}`", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to get DP for `{username}`:\n`{e}`", parse_mode="Markdown")
            
    bot.send_message(message.chat.id, "🎉 Finished updating all Profile Pictures!")

@bot.message_handler(content_types=['video'])
def handle_video(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    accounts = load_accounts()
    if not accounts:
        bot.reply_to(message, "❌ No accounts found! Please add them via the Web Dashboard or /import.")
        return

    msg = bot.reply_to(message, "📥 Downloading video from Telegram...")
    video_path = f"downloads/temp_video_{message.message_id}.mp4"
    
    try:
        file_info = bot.get_file(message.video.file_id)
        video_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        with open(video_path, "wb") as f:
            f.write(requests.get(video_url).content)
        
        bot.edit_message_text(f"✅ Video downloaded! Starting upload to {len(accounts)} accounts...", chat_id=message.chat.id, message_id=msg.message_id)
        
        for username, data in accounts.items():
            try:
                bot.send_message(message.chat.id, f"⏳ `[{username}]` Logging in...", parse_mode="Markdown")
                
                cl = Client()
                cl.login_by_sessionid(data["session_string"])
                
                dp_path = f"downloads/{username}_dp.jpg"
                
                if not os.path.exists(dp_path):
                    bot.send_message(message.chat.id, f"📸 `[{username}]` DP not saved. Downloading it once...", parse_mode="Markdown")
                    user_info = cl.user_info(cl.user_id)
                    with open(dp_path, "wb") as f:
                        f.write(requests.get(user_info.profile_pic_url).content)
                
                bot.send_message(message.chat.id, f"🚀 `[{username}]` Uploading Reel...", parse_mode="Markdown")
                media = cl.clip_upload(
                    path=video_path,
                    caption=data.get("caption", "Uploaded via bot"),
                    thumbnail=dp_path
                )
                
                reel_url = f"https://www.instagram.com/reel/{media.code}/"
                bot.send_message(message.chat.id, f"✅ *Success:* `{username}`\n🔗 {reel_url}", parse_mode="Markdown", disable_web_page_preview=True)
                
                time.sleep(15)
                
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ *Error on {username}:*\n`{e}`", parse_mode="Markdown")
                
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        bot.send_message(message.chat.id, "🎉 All uploads finished for this video!")

# ==========================================
# 🌐 FLASK WEB DASHBOARD
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Account Manager</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: auto; background: #f4f6f9; }
        .card { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 6px; background: white; }
        input[type="text"], textarea, button { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        .btn { background: #28a745; color: white; border: none; cursor: pointer; font-weight: bold; border-radius: 4px; padding: 10px;}
        .btn-blue { background: #007bff; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        .delete-btn { color: white; background: #dc3545; padding: 5px 10px; text-decoration: none; border-radius: 4px; font-size: 12px; }
        .flex-container { display: flex; gap: 20px; }
        .flex-child { flex: 1; }
    </style>
</head>
<body>
    <h2>Instagram Bot Dashboard</h2>
    
    <div class="flex-container">
        <div class="card flex-child">
            <h3>➕ Add or Edit Account</h3>
            <p><small>Note: If you enter an existing username, it will update that account's session and caption.</small></p>
            <form action="/add" method="post">
                <label>Instagram Username:</label>
                <input type="text" name="username" placeholder="e.g., moviemore709" required>
                
                <label>Session String (Cookie):</label>
                <textarea name="session_string" rows="3" placeholder="Paste session string here..." required></textarea>
                
                <label>Default Caption:</label>
                <textarea name="caption" rows="2" placeholder="e.g., Watch this! 🔥 #viral" required></textarea>
                
                <button type="submit" class="btn">Save Account</button>
            </form>
        </div>

        <div class="card flex-child">
            <h3>📥 Import / Export Backup</h3>
            <p><small>Upload an exported <b>accounts.json</b> file to instantly restore your data.</small></p>
            <form action="/import_web" method="post" enctype="multipart/form-data">
                <input type="file" name="backup_file" accept=".json" required style="margin: 15px 0;">
                <button type="submit" class="btn btn-blue">Import Data</button>
            </form>
            <hr style="margin: 20px 0; border: 0; border-top: 1px solid #eee;">
            <a href="/export_web" style="text-decoration: none;">
                <button class="btn" style="background: #17a2b8;">Download Backup (JSON)</button>
            </a>
        </div>
    </div>

    <div class="card">
        <h3>📋 Configured Accounts ({{ accounts|length }})</h3>
        <table>
            <tr>
                <th>Username</th>
                <th>Caption</th>
                <th>Action</th>
            </tr>
            {% for user, data in accounts.items() %}
            <tr>
                <td><strong>{{ user }}</strong></td>
                <td>{{ data.caption }}</td>
                <td><a class="delete-btn" href="/delete/{{ user }}">Delete</a></td>
            </tr>
            {% else %}
            <tr><td colspan="3">No accounts configured yet. Use the form above to add one.</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    accounts = load_accounts()
    return render_template_string(HTML_TEMPLATE, accounts=accounts)

@app.route('/add', methods=['POST'])
def add_account():
    username = request.form.get("username").strip()
    session_string = request.form.get("session_string").strip()
    caption = request.form.get("caption").strip()
    
    accounts = load_accounts()
    
    accounts[username] = {
        "session_string": session_string,
        "caption": caption
    }
    
    save_accounts(accounts)
    return redirect('/')

@app.route('/delete/<username>')
def delete_account(username):
    accounts = load_accounts()
    if username in accounts:
        del accounts[username]
        save_accounts(accounts)
        
        dp_path = f"downloads/{username}_dp.jpg"
        if os.path.exists(dp_path):
            os.remove(dp_path)
            
    return redirect('/')

@app.route('/import_web', methods=['POST'])
def import_web():
    if 'backup_file' not in request.files:
        return redirect('/')
        
    file = request.files['backup_file']
    if file.filename == '':
        return redirect('/')
        
    if file and file.filename.endswith('.json'):
        try:
            # Read the uploaded file and parse JSON
            data = json.load(file)
            save_accounts(data)
        except Exception as e:
            print(f"Error importing JSON: {e}")
            
    return redirect('/')

@app.route('/export_web')
def export_web():
    from flask import send_file
    if os.path.exists(ACCOUNTS_FILE):
        return send_file(ACCOUNTS_FILE, as_attachment=True, download_name="accounts_backup.json")
    return redirect('/')

def run_bot():
    print("Starting Telegram Bot thread...")
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    
    print("Starting Web Dashboard...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
