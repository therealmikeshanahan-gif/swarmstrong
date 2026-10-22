/**
 * Reply classifier — direct port of src/agsleads/reply_guard.py.
 *
 * The Python version is the tested reference (50 tests). This file must stay
 * behaviourally identical to it; apps-script/parity.test.mjs runs both against
 * the same fixtures and fails if they ever disagree, and
 * tests/test_config_drift.py fails if the address lists below drift from
 * config/identities.yml.
 *
 * Plain function declarations and `var` on purpose: Apps Script concatenates
 * .gs files into one global scope and does not support modules.
 */

// ---------------------------------------------------------------------------
// Who we are. Add a new sending domain here the SAME DAY you add it to
// Instantly, or the false alerts come back.
// ---------------------------------------------------------------------------

var OWNED_DOMAINS = [
  'teamarmoredglass.com',
  'armoredglassgrants.com',
  'armoredglasssolutions.com'
];

var OWNED_ADDRESSES = [
  'clark@teamarmoredglass.com',
  'clark.shanahan@teamarmoredglass.com',
  'shanahan@teamarmoredglass.com',
  'julia@armoredglassgrants.com',
  'mike@armoredglassgrants.com',
  'armorglass@icloud.com',
  'clarkshanahan@icloud.com',
  'therealmikeshanahan@gmail.com',
  'juliapaquette@yahoo.com',
  'juliacpaquette@yahoo.com',
  'julcpaq@gmail.com'
];

var OWN_CONTENT_MARKERS = [
  'CA Contractor License #997737',
  'Reply "no thanks" to opt out',
  '21515 Hawthorne Blvd, Suite 200',
  'Last follow-up from me'
];

// ---------------------------------------------------------------------------

var BOUNCE_SENDERS = ['mailer-daemon', 'postmaster', 'no-reply@', 'noreply@'];

var BOUNCE_SUBJECTS = [
  'undeliverable', 'undelivered mail', 'delivery status notification',
  'returned mail', 'mail delivery failed', 'address not found',
  'delivery incomplete'
];

var BOUNCE_CONTENT_TYPES = ['multipart/report', 'message/delivery-status'];

var AUTOREPLY_SUBJECTS = [
  'out of office', 'automatic reply', 'auto-reply', 'autoreply',
  'away from', 'on vacation', 'maternity leave', 'no longer with'
];

var AUTOREPLY_BODY = [
  'out of the office', 'out of office', 'automatic reply',
  'i am currently away', 'currently out of', 'will be out until',
  'no longer with the company', 'no longer employed',
  'thank you for your email, i am', 'this is an automated',
  'do not reply to this message'
];

var OPT_OUT_PATTERNS = [
  /\bno\s*thanks\b/,
  /\bunsubscribe\b/,
  /\bremove me\b/,
  /\btake me off\b/,
  /\bstop (?:emailing|contacting)\b/,
  /\bdo not (?:contact|email)\b/,
  /\bopt[- ]?out\b/
];

var ADDR_RE = /[\w.+-]+@[\w-]+\.[\w.-]+/g;

function extractAddresses(headerValue) {
  if (!headerValue) return [];
  var found = String(headerValue).match(ADDR_RE);
  if (!found) return [];
  return found.map(function (a) { return a.toLowerCase(); });
}

function ownsAddress(address) {
  if (!address) return false;
  var addr = String(address).trim().toLowerCase();
  if (OWNED_ADDRESSES.indexOf(addr) !== -1) return true;
  var at = addr.indexOf('@');
  if (at === -1) return false;
  return OWNED_DOMAINS.indexOf(addr.slice(at + 1)) !== -1;
}

function ownsAny(headerValue) {
  return extractAddresses(headerValue).some(ownsAddress);
}

function bodyLooksLikeOurs(body) {
  if (!body) return false;
  var low = String(body).toLowerCase();
  return OWN_CONTENT_MARKERS.some(function (m) {
    return low.indexOf(m.toLowerCase()) !== -1;
  });
}

function containsAny(haystack, needles) {
  var low = String(haystack || '').toLowerCase();
  return needles.some(function (n) { return low.indexOf(n) !== -1; });
}

function detectOptOut(body) {
  var low = String(body || '').toLowerCase();
  return OPT_OUT_PATTERNS.some(function (p) { return p.test(low); });
}

/**
 * Classify one message.
 *
 * Order matters. Step 1 is the fix for the Oct 12 false alerts, and it runs
 * before opt-out detection because our own copy ends with
 * 'Reply "no thanks" to opt out' — the other order marks our own prospects as
 * opted out and silently burns the list.
 *
 * @return {{kind: string, alert: boolean, reason: string,
 *           responder: ?string, optOut: boolean}}
 */
function classifyReply(fields) {
  var from = fields.from || '';
  var to = fields.to || '';
  var subject = fields.subject || '';
  var contentType = fields.contentType || '';
  var body = fields.body || '';

  var senders = extractAddresses(from);
  var responder = senders.length ? senders[0] : null;

  function verdict(kind, alert, reason, optOut) {
    return {
      kind: kind,
      alert: alert,
      reason: reason,
      responder: responder,
      optOut: !!optOut
    };
  }

  // 1. Our own mail. Never alert, whatever the subject says.
  if (ownsAny(from)) {
    return verdict('outbound_self', false,
      'From ' + responder + ' is one of our sending identities', false);
  }

  // 1b. A forward can strip the real From. If the body is clearly our copy
  // and the recipient is not us, it is still our mail.
  if (bodyLooksLikeOurs(body) && !ownsAny(to)) {
    return verdict('outbound_self', false,
      'body matches our own sequence copy', false);
  }

  // 2. Bounces.
  if (containsAny(from, BOUNCE_SENDERS) ||
      containsAny(subject, BOUNCE_SUBJECTS) ||
      containsAny(contentType, BOUNCE_CONTENT_TYPES)) {
    return verdict('bounce', false, 'delivery status notification', false);
  }

  var optOut = detectOptOut(body);

  // 3. Autoresponders. Logged, not paged.
  var autoSubmitted = String(fields.autoSubmitted || '').toLowerCase();
  if (autoSubmitted.indexOf('auto-') === 0) {
    return verdict('autoreply', false, 'auto-submitted: ' + autoSubmitted, optOut);
  }
  if (fields.xAutoreply) {
    return verdict('autoreply', false, 'x-autoreply header present', optOut);
  }
  var precedence = String(fields.precedence || '').toLowerCase();
  if (['bulk', 'auto_reply', 'junk', 'list'].indexOf(precedence) !== -1) {
    return verdict('autoreply', false, 'precedence: ' + precedence, optOut);
  }
  if (containsAny(subject, AUTOREPLY_SUBJECTS) || containsAny(body, AUTOREPLY_BODY)) {
    return verdict('autoreply', false, 'out-of-office / automated wording', optOut);
  }

  // 4. A human at the prospect wrote this.
  return verdict('human_reply', true,
    'human reply — answer within 1 business hour', optOut);
}
