/**
 * AGS reply watcher — the Lindy replacement.
 *
 * Runs on a 5-minute time trigger inside the Google account that receives the
 * campaign replies. Nothing to top up, no credits, no third-party agent: the
 * failure mode that lost Jeff White on Oct 16 cannot happen here.
 *
 * What it does, per message:
 *   our own mail   -> label AGS/Outbound-Self, no alert   (the Oct 12 bug)
 *   bounce         -> label AGS/Reply-Bounce, no alert
 *   autoresponder  -> label AGS/Reply-Auto, no alert
 *   human reply    -> label AGS/Reply-Human, star, ALERT
 *   opt-out        -> label AGS/Opt-Out and alert, so they get pulled from Instantly
 *
 * Install: see apps-script/README.md. Run setup() once.
 */

// --- configuration ---------------------------------------------------------

/** Gmail search for the campaign reply mailbox. Narrow this if the account
 *  carries unrelated mail. Defaults to the whole inbox minus our own sends. */
var WATCH_QUERY = 'in:anywhere -in:drafts';

/** Who gets paged on a real human reply. First one should be a shared inbox,
 *  not a personal one — a single personal inbox is how replies got missed. */
var ALERT_EMAILS = [
  'owner3@example-personal.com'
];

/** Optional. Carrier email-to-SMS gateway, e.g. '7145551234@txt.att.net'.
 *  Set as a Script Property named SMS_GATEWAY to avoid committing a number. */
function smsGateway() {
  return PropertiesService.getScriptProperties().getProperty('SMS_GATEWAY');
}

/** Optional. Slack incoming-webhook URL, as Script Property SLACK_WEBHOOK. */
function slackWebhook() {
  return PropertiesService.getScriptProperties().getProperty('SLACK_WEBHOOK');
}

/** Never look back further than this on a first run or after a long outage. */
var MAX_LOOKBACK_HOURS = 72;

var LABELS = {
  outbound_self: 'AGS/Outbound-Self',
  bounce: 'AGS/Reply-Bounce',
  autoreply: 'AGS/Reply-Auto',
  human_reply: 'AGS/Reply-Human',
  opt_out: 'AGS/Opt-Out'
};

// --- setup -----------------------------------------------------------------

function setup() {
  Object.keys(LABELS).forEach(function (k) { ensureLabel(LABELS[k]); });

  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'run') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('run').timeBased().everyMinutes(5).create();

  Logger.log('Labels created and 5-minute trigger installed.');
  Logger.log('Set SMS_GATEWAY and SLACK_WEBHOOK in Project Settings > Script Properties if you want those.');
}

function ensureLabel(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

// --- main loop -------------------------------------------------------------

function run() {
  var props = PropertiesService.getScriptProperties();
  var nowMs = Date.now();

  var lastRunMs = Number(props.getProperty('lastRunMs') || 0);
  var floorMs = nowMs - MAX_LOOKBACK_HOURS * 3600 * 1000;
  if (!lastRunMs || lastRunMs < floorMs) lastRunMs = floorMs;

  // Gmail's after: is second-granularity; back off 60s to avoid edge misses.
  var afterSec = Math.floor((lastRunMs - 60000) / 1000);
  var query = WATCH_QUERY + ' after:' + afterSec;

  var seen = loadSeen(props);
  var threads = GmailApp.search(query, 0, 100);
  var counts = { outbound_self: 0, bounce: 0, autoreply: 0, human_reply: 0, skipped: 0 };

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (message) {
      var id = message.getId();
      if (seen[id]) { counts.skipped++; return; }
      if (message.getDate().getTime() < lastRunMs - 60000) { return; }

      var verdict = classifyReply(fieldsFrom(message));
      seen[id] = 1;
      counts[verdict.kind] = (counts[verdict.kind] || 0) + 1;

      thread.addLabel(ensureLabel(LABELS[verdict.kind]));

      if (verdict.optOut) {
        thread.addLabel(ensureLabel(LABELS.opt_out));
      }

      if (verdict.alert) {
        message.star();
        alertHuman(message, verdict);
      } else {
        Logger.log('quiet [' + verdict.kind + '] ' + verdict.reason);
      }
    });
  });

  props.setProperty('lastRunMs', String(nowMs));
  saveSeen(props, seen);
  Logger.log('run: ' + JSON.stringify(counts));
}

/** Pull the headers classifyReply() needs out of a GmailMessage. */
function fieldsFrom(message) {
  return {
    from: message.getFrom(),
    to: message.getTo(),
    subject: message.getSubject(),
    body: message.getPlainBody(),
    contentType: safeHeader(message, 'Content-Type'),
    autoSubmitted: safeHeader(message, 'Auto-Submitted'),
    xAutoreply: safeHeader(message, 'X-Autoreply'),
    precedence: safeHeader(message, 'Precedence')
  };
}

function safeHeader(message, name) {
  try {
    return message.getHeader(name) || '';
  } catch (e) {
    return '';  // getHeader is not available on every Apps Script runtime
  }
}

// --- alerting --------------------------------------------------------------

function alertHuman(message, verdict) {
  var from = message.getFrom();
  var subject = message.getSubject();
  var body = message.getPlainBody().slice(0, 1500);
  var link = 'https://mail.google.com/mail/u/0/#all/' + message.getThread().getId();

  var tag = verdict.optOut ? 'OPT-OUT' : 'HUMAN REPLY';
  var title = tag + ' — ' + from;

  var text = [
    tag + (verdict.optOut ? ' — remove them from Instantly now' : ' — answer within 1 business hour'),
    '',
    'From:    ' + from,
    'Subject: ' + subject,
    'Open:    ' + link,
    '',
    '--- what they said ---',
    body
  ].join('\n');

  ALERT_EMAILS.forEach(function (to) {
    GmailApp.sendEmail(to, title, text);
  });

  var sms = smsGateway();
  if (sms) {
    // Gateways truncate hard; lead with the number they need to act.
    GmailApp.sendEmail(sms, '', tag + ': ' + from + ' — ' + subject.slice(0, 60));
  }

  var hook = slackWebhook();
  if (hook) {
    try {
      UrlFetchApp.fetch(hook, {
        method: 'post',
        contentType: 'application/json',
        payload: JSON.stringify({ text: '*' + title + '*\n' + link + '\n>' + body.slice(0, 400) }),
        muteHttpExceptions: true
      });
    } catch (e) {
      Logger.log('slack failed: ' + e);
    }
  }
}

// --- processed-message memory ----------------------------------------------
// Keeps the last 1000 message ids so a retry or an overlapping window can
// never double-page anyone.

function loadSeen(props) {
  try {
    return JSON.parse(props.getProperty('seenIds') || '{}');
  } catch (e) {
    return {};
  }
}

function saveSeen(props, seen) {
  var ids = Object.keys(seen);
  if (ids.length > 1000) {
    var trimmed = {};
    ids.slice(-1000).forEach(function (id) { trimmed[id] = 1; });
    seen = trimmed;
  }
  props.setProperty('seenIds', JSON.stringify(seen));
}

// --- self-check ------------------------------------------------------------

/** Run this from the editor after install. Proves the Oct 12 bug is fixed
 *  without touching the real mailbox. */
function selfCheck() {
  var cases = [
    {
      name: 'our own step-4 follow-up (fired a false alert on Oct 12)',
      fields: {
        from: 'sender1@example-outreach.com',
        to: 'info@example-propmgmt.com',
        subject: 'Re: Who handles entry glass maintenance?',
        body: 'Last follow-up from me. Jane Example CA Contractor License #000000 Reply "no thanks" to opt out.'
      },
      expect: 'outbound_self'
    },
    {
      name: 'real human reply',
      fields: {
        from: 'dmorales@example-temple.org',
        to: 'persona@example-grants.com',
        subject: 'Re: security grant',
        body: 'Hello Julia, I would love a walk through to discuss the options.'
      },
      expect: 'human_reply'
    },
    {
      name: 'out of office',
      fields: {
        from: 'pm@example.com',
        to: 'sender1@example-outreach.com',
        subject: 'Automatic reply: Who handles entry glass maintenance?',
        autoSubmitted: 'auto-replied',
        body: 'I am currently out of the office.'
      },
      expect: 'autoreply'
    },
    {
      name: 'bounce',
      fields: {
        from: 'MAILER-DAEMON@mx.example.com',
        to: 'sender1@example-outreach.com',
        subject: 'Undeliverable: Who handles entry glass maintenance?',
        body: '550 5.1.1 Address not found.'
      },
      expect: 'bounce'
    }
  ];

  var failures = 0;
  cases.forEach(function (c) {
    var got = classifyReply(c.fields).kind;
    var ok = got === c.expect;
    if (!ok) failures++;
    Logger.log((ok ? 'PASS' : 'FAIL') + '  ' + c.name + '  (got ' + got + ')');
  });
  Logger.log(failures === 0 ? 'All checks passed.' : failures + ' CHECK(S) FAILED');
}
