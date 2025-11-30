from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler
from datetime import datetime
import asyncio
import os

from db import db
from vars import *

async def handle_subscription_end(client: Client, user_id: int):
    try:
        await client.send_message(
            user_id,
            "**⚠️ Subscription Ended**\n"
            "Your access has expired. Contact admin to renew."
        )
    except Exception:
        pass

async def broadcast_bot_available(client: Client, bot_username: str):
    """Broadcast to all users that bot is available"""
    try:
        user_ids = db.get_all_users_with_subscriptions(bot_username)
        message = "**✅ Bot available now**\n\nYou can now use the bot!"
        
        sent_count = 0
        for user_id in user_ids:
            try:
                await client.send_message(user_id, message)
                sent_count += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception:
                continue
        
        print(f"Broadcast sent to {sent_count} users")
    except Exception as e:
        print(f"Error broadcasting: {str(e)}")

# Command to add a new user
async def add_user_cmd(client: Client, message: Message):
    """Add a new user to the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text(AUTH_MESSAGES["not_admin"])
            return

        # Parse command arguments
        args = message.text.split()[1:]
        if len(args) != 2:
            await message.reply_text(
                AUTH_MESSAGES["invalid_format"].format(
                    format="/add user_id days\n\nExample:\n/add 123456789 30"
                )
            )
            return

        user_id = int(args[0])
        days = int(args[1])

        # Get bot username
        bot_username = client.me.username

        try:
            # Try to get user info from Telegram
            user = await client.get_users(user_id)
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
        except:
            # If can't get user info, use ID as name
            name = f"User {user_id}"

        # Add user to database with bot username
        success, expiry_date = db.add_user(user_id, name, days, bot_username)
        
        if success:
            # Format expiry date
            expiry_str = expiry_date.strftime("%d-%m-%Y %H:%M:%S")
            
            # Send success message to admin using template
            await message.reply_text(
                AUTH_MESSAGES["user_added"].format(
                    name=name,
                    user_id=user_id,
                    expiry_date=expiry_str
                )
            )

            # Try to notify the user using template
            try:
                await client.send_message(
                    user_id,
                    AUTH_MESSAGES["subscription_active"].format(
                        expiry_date=expiry_str
                    )
                )
            except Exception as e:
                print(f"Failed to notify user {user_id}: {str(e)}")
        else:
            await message.reply_text("❌ Failed to add user. Please try again.")

    except ValueError:
        await message.reply_text("❌ Invalid user ID or days. Please use numbers only.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to remove a user
async def remove_user_cmd(client: Client, message: Message):
    """Remove a user from the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("❌ Not authorized to remove users.")
            return

        # Parse command arguments
        args = message.text.split()[1:]
        if len(args) != 1:
            await message.reply_text(
                "❌ Invalid format!\n"
                "Use: /remove user_id\n"
                "Example: /remove 123456789"
            )
            return

        user_id = int(args[0])
        
        # Remove user from database
        if db.remove_user(user_id, client.me.username):
            await message.reply_text(f"✅ User {user_id} removed.")
        else:
            await message.reply_text(f"❌ User {user_id} not found.")

    except ValueError:
        await message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to list all users
async def list_users_cmd(client: Client, message: Message):
    """List all users of the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("❌ Not authorized to list users.")
            return

        users = db.list_users(client.me.username)
        
        if not users:
            await message.reply_text("📝 No users found.")
            return

        # Format user list
        user_list = "**📝 Users List**\n\n"
        for user in users:
            expiry = user['expiry_date']
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            days_left = (expiry - datetime.now()).days
            
            user_list += (
                f"• Name: {user['name']}\n"
                f"• ID: {user['user_id']}\n"
                f"• Days Left: {days_left}\n"
                f"• Expires: {expiry.strftime('%d-%m-%Y')}\n"
                f"───────────────\n"
            )

        await message.reply_text(user_list)

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to check user's plan
async def my_plan_cmd(client: Client, message: Message):
    """Show user's current plan details"""
    try:
        user = db.get_user(message.from_user.id, client.me.username)
        
        if not user:
            await message.reply_text("❌ No active plan.")
            return

        expiry = user['expiry_date']
        if isinstance(expiry, str):
            expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = (expiry - datetime.now()).days

        await message.reply_text(
            f"**📱 Plan Details**\n\n"
            f"• Name: {user['name']}\n"
            f"• Days Left: {days_left}\n"
            f"• Expires: {expiry.strftime('%d-%m-%Y')}"
        )

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to claim free 2-hour subscription
async def free_cmd(client: Client, message: Message):
    """Claim a free 2-hour subscription"""
    try:
        user_id = message.from_user.id
        bot_username = client.me.username
        
        # Check if user is admin (admins always have access)
        if db.is_admin(user_id):
            await message.reply_text("✅ You are an admin. You have unlimited access.")
            return
        
        # Get user name
        try:
            user = await client.get_users(user_id)
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
        except:
            name = f"User {user_id}"
        
        # Check if bot is already in use
        active = db.get_active_user(bot_username)
        if active:
            active_user_id = active.get('user_id')
            if active_user_id == user_id:
                # Same user, show current status
                expiry = active.get('expiry_date')
                if isinstance(expiry, str):
                    expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                
                remaining_time = expiry - datetime.now()
                hours = int(remaining_time.total_seconds() // 3600)
                minutes = int((remaining_time.total_seconds() % 3600) // 60)
                upload_count = active.get('upload_count', 0)
                
                await message.reply_text(
                    f"**✅ You are currently using the bot!**\n\n"
                    f"• Time Remaining: {hours}h {minutes}m\n"
                    f"• Links Uploaded: {upload_count}/100\n"
                    f"• Expires: {expiry.strftime('%d-%m-%Y %H:%M:%S')}"
                )
            else:
                # Different user is using the bot - show remaining time
                expiry = active.get('expiry_date')
                if isinstance(expiry, str):
                    expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                
                remaining_time = expiry - datetime.now()
                if remaining_time.total_seconds() > 0:
                    hours = int(remaining_time.total_seconds() // 3600)
                    minutes = int((remaining_time.total_seconds() % 3600) // 60)
                    seconds = int(remaining_time.total_seconds() % 60)
                    
                    time_str = ""
                    if hours > 0:
                        time_str += f"{hours}h "
                    if minutes > 0:
                        time_str += f"{minutes}m "
                    if seconds > 0 and hours == 0:  # Only show seconds if less than an hour
                        time_str += f"{seconds}s"
                    
                    await message.reply_text(
                        f"❌ **Bot is currently in use**\n\n"
                        f"Another user is using the bot right now.\n\n"
                        f"⏰ **Bot will be available in:** {time_str.strip() or '0s'}\n"
                        f"🕐 **Available at:** {expiry.strftime('%d-%m-%Y %H:%M:%S')}\n\n"
                        f"Please try again when the bot becomes available."
                    )
                else:
                    await message.reply_text(
                        "❌ **Bot is currently in use**\n\n"
                        "Another user is using the bot right now. Please try again later when the bot becomes available."
                    )
                return
        
        # Check if user can claim free subscription today
        if not db.can_claim_free_subscription(user_id, bot_username):
            free_sub = db.get_free_subscription_info(user_id, bot_username)
            last_claimed = free_sub.get('last_claimed_date') if free_sub else None
            if last_claimed:
                if isinstance(last_claimed, str):
                    last_claimed = datetime.strptime(last_claimed, "%Y-%m-%d %H:%M:%S")
                await message.reply_text(
                    f"❌ **Daily limit reached**\n\n"
                    f"You have already used your free 2-hour subscription today.\n"
                    f"Last claimed: {last_claimed.strftime('%d-%m-%Y %H:%M:%S')}\n\n"
                    f"You can claim again tomorrow!"
                )
                return
        
        # Claim free subscription
        success, expiry_date = db.claim_free_subscription(user_id, name, bot_username)
        
        if success:
            expiry_str = expiry_date.strftime("%d-%m-%Y %H:%M:%S")
            await message.reply_text(
                f"**🎉 Free Subscription Activated!**\n\n"
                f"• Duration: 2 hours\n"
                f"• Upload Limit: 100 links\n"
                f"• Expires: {expiry_str}\n\n"
                f"**Note:** Only you can use the bot during this period. When it expires, all users will be notified."
            )
        else:
            await message.reply_text(
                "❌ **Failed to activate subscription**\n\n"
                "The bot might be currently in use by another user. Please try again later."
            )

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Register command handlers
add_user_handler = filters.command("add") & filters.private, add_user_cmd
remove_user_handler = filters.command("remove") & filters.private, remove_user_cmd
list_users_handler = filters.command("users") & filters.private, list_users_cmd
my_plan_handler = filters.command("plan") & filters.private, my_plan_cmd
free_handler = filters.command("free") & filters.private, free_cmd

# Decorator for checking user authorization
def check_auth():
    def decorator(func):
        async def wrapper(client, message, *args, **kwargs):
            bot_info = await client.get_me()
            bot_username = bot_info.username
            if not db.is_user_authorized(message.from_user.id, bot_username):
                return await message.reply(
                    "**❌ Access Denied**\n"
                    "Contact admin to get access."
                )
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator 
