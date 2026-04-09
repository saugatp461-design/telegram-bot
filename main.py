const { Telegraf, Markup } = require('telegraf');
const admin = require('firebase-admin');
const express = require('express');
require('dotenv').config();

// 1. Initialize Firebase Admin
const serviceAccount = require("./serviceAccountKey.json");
admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
    databaseURL: "https://silverscreen-b5971-default-rtdb.asia-southeast1.firebasedatabase.app"
});
const db = admin.firestore();

// 2. Initialize Bot & Config
const bot = new Telegraf(process.env.BOT_TOKEN);
const app = express();
const REQUIRED_CHANNELS = ['@SFlixChannels', '@MyBackupChannel']; // Usernames or IDs
const WEB_APP_URL = 'https://your-mini-app-url.com'; // URL where your HTML is hosted

// --- Helper: Check Subscription ---
async function isSubscribed(ctx) {
    for (const channel of REQUIRED_CHANNELS) {
        try {
            const member = await ctx.telegram.getChatMember(channel, ctx.from.id);
            if (['left', 'kicked', 'restricted'].includes(member.status)) return false;
        } catch (e) {
            console.error("Error checking sub:", e);
            return false;
        }
    }
    return true;
}

// --- Command: /start ---
bot.start(async (ctx) => {
    const userId = ctx.from.id.toString();
    const startPayload = ctx.startPayload; // This catches the Referral Code

    // Check if user exists in Firebase
    const userRef = db.collection('users').doc(userId);
    const userDoc = await userRef.get();

    // Handle New User & Referral
    if (!userDoc.exists) {
        let inviterId = null;
        if (startPayload && startPayload.length > 5) {
            // Find inviter by their referral code
            const inviterQuery = await db.collection('users').where('referralCode', '==', startPayload).limit(1).get();
            if (!inviterQuery.empty) {
                inviterId = inviterQuery.docs[0].id;
            }
        }

        // Create User
        await userRef.set({
            username: ctx.from.username || ctx.from.first_name,
            credits: 1, // Starting credits
            referralCode: Math.random().toString(36).substring(7).toUpperCase(),
            usedRef: !!inviterId,
            history: [],
            likedMovies: [],
            subscriptions: {},
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        // Reward Inviter
        if (inviterId) {
            const rewardsRef = db.collection('settings').doc('rewards');
            const rewardsSnap = await rewardsRef.get();
            const rewardAmt = rewardsSnap.exists ? rewardsSnap.data().inviter : 100;

            await db.collection('users').doc(inviterId).update({
                credits: admin.firestore.FieldValue.increment(rewardAmt)
            });
        }
    }

    // Check Membership
    const subscribed = await isSubscribed(ctx);

    if (!subscribed) {
        return ctx.replyWithMarkdownV2(
            `👋 *Welcome to SFlix\\!*\n\nTo use this app and get your free credits, you must join our channels first\\.`,
            Markup.inlineKeyboard([
                [Markup.button.url('Join Channel 1', 'https://t.me/SFlixChannels')],
                [Markup.button.url('Join Channel 2', 'https://t.me/MyBackupChannel')],
                [Markup.button.callback('✅ I have joined', 'check_sub')]
            ])
        );
    }

    // Welcome Message if Subscribed
    ctx.reply(
        `Welcome back, ${ctx.from.first_name}! 🍿\nReady to watch some Premium Telegram content?`,
        Markup.keyboard([
            [Markup.button.webApp('🚀 Open SFlix App', WEB_APP_URL)]
        ]).resize()
    );
});

// --- Action: Check Subscription Button ---
bot.action('check_sub', async (ctx) => {
    const subscribed = await isSubscribed(ctx);
    if (subscribed) {
        await ctx.answerCbQuery("Success! You can now open the app.");
        ctx.reply(
            "✅ Thank you for joining! Click below to start:",
            Markup.keyboard([
                [Markup.button.webApp('🚀 Open SFlix App', WEB_APP_URL)]
            ]).resize()
        );
    } else {
        await ctx.answerCbQuery("❌ You haven't joined all channels yet!", { show_alert: true });
    }
});

// Start Bot
bot.launch();
console.log("SFlix Backend Bot is running...");

// Express for health checks (Render/Heroku requirements)
app.get('/', (req, res) => res.send('Bot is Alive'));
app.listen(process.env.PORT || 3000);
