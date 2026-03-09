/**
 * GOOGLE APPS SCRIPT: AI RECRUITER LABELER & SYNCER (Self-Hosted Edition)
 * * Instructions:
 * 1. Ensure your instance at https://llama.davidfan.me is accessible.
 * 2. In Apps Script, go to Project Settings (cog icon) -> Script Properties.
 * 3. Add properties: 
 * - LLM_API_KEY (if required by the API)
 * - LLM_USER (for .htaccess / Basic Auth)
 * - LLM_PASS (for .htaccess / Basic Auth)
 * 4. Set a Trigger to run 'mainPipeline' daily (or every 30 mins).
 */

const CONFIG = {
  LABEL_NAME: '! Jobs/2026',
  API_URL: 'https://llama.davidfan.me/v1/chat/completions',
  MODEL_NAME: 'gpt-oss-120b', 
  SYSTEM_PROMPT: `You are an expert recruitment assistant. Analyze the email content provided.
  Determine if it is a message from a recruiter, hiring manager, or talent acquisition professional 
  reaching out about a specific job opportunity or scheduling an interview.
  
  EXCLUDE: Automated job alerts, newsletters, LinkedIn "suggested jobs", or rejection emails.
  INCLUDE: Personalized outreach, requests for your resume, or invitations to interview.
  
  Respond ONLY with a JSON object: {"isRecruiter": true/false}`,
  BASE_SEARCH: 'is:unread -label:"! Jobs/2026" (category:primary OR category:updates)',
  FETCH_BATCH_SIZE: 50, 
  PARALLEL_LIMIT: 10,    // Number of concurrent requests to keep in flight
  MAX_TOTAL_THREADS: 200 // Maximum to process in one execution (to avoid 6min timeout)
};

/**
 * Main function to run via Trigger.
 */
async function mainPipeline() {
  const lastRunTime = getLastRunTimestamp();

  // If no last run, look back 7 days.
  const timeQuery = lastRunTime ? `after:${lastRunTime}` : 'newer_than:7d';
  const fullQuery = `${CONFIG.BASE_SEARCH} ${timeQuery}`;
  
  console.log(`Searching with query: ${fullQuery}`);

  // This will now handle checkpointing internally per-email
  await classifyAllRecruiterEmails(fullQuery);
  
  syncEmailsByLabel();
}

/**
 * DEBUG ENTRYPOINT
 */
async function debugClassifyRecent() {
  console.log("Starting debug classification on 5 most recent threads...");
  const debugQuery = "is:unread newer_than:1d"; 
  await classifyAllRecruiterEmails(debugQuery, 5);
  console.log("Debug run complete.");
}

/**
 * Processes all email threads matching the query.
 * Implements a worker pool to keep PARALLEL_LIMIT requests in flight.
 * Updates checkpoint in real-time as consecutive tasks complete.
 */
async function classifyAllRecruiterEmails(query, limitOverride = null) {
  let allThreads = [];
  let start = 0;
  const maxToFetch = limitOverride || CONFIG.MAX_TOTAL_THREADS;

  // 1. Fetch matching threads
  while (allThreads.length < 1000) { 
    const batch = GmailApp.search(query, start, CONFIG.FETCH_BATCH_SIZE);
    if (batch.length === 0) break;
    allThreads = allThreads.concat(batch);
    start += CONFIG.FETCH_BATCH_SIZE;
  }

  if (allThreads.length === 0) return;

  // IMPORTANT: Sort oldest to newest for checkpointing
  allThreads.sort((a, b) => a.getLastMessageDate().getTime() - b.getLastMessageDate().getTime());
  
  if (allThreads.length > maxToFetch) {
    allThreads = allThreads.slice(0, maxToFetch);
  }
  
  console.log(`Total threads to process (oldest first): ${allThreads.length}`);

  const targetLabel = getOrCreateLabel(CONFIG.LABEL_NAME);
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty('LLM_API_KEY') || 'sk-no-key-required';
  const authUser = props.getProperty('LLM_USER');
  const authPass = props.getProperty('LLM_PASS');

  const headers = { "Authorization": `Bearer ${apiKey}` };
  if (authUser && authPass) {
    headers["Authorization"] = `Basic ${Utilities.base64Encode(`${authUser}:${authPass}`)}`;
  }

  // --- Real-time Checkpointing State ---
  let nextToAssign = 0;
  let highestConsecutiveFinished = -1;
  const status = new Array(allThreads.length).fill(false);

  /**
   * Checks if we can advance the global checkpoint based on finished tasks.
   */
  const advanceCheckpoint = () => {
    let advanced = false;
    while (highestConsecutiveFinished + 1 < allThreads.length && status[highestConsecutiveFinished + 1]) {
      highestConsecutiveFinished++;
      advanced = true;
    }

    if (advanced && highestConsecutiveFinished >= 0) {
      const lastSafeThread = allThreads[highestConsecutiveFinished];
      const newTimestamp = Math.floor(lastSafeThread.getLastMessageDate().getTime() / 1000) + 1;
      updateLastRunTimestamp(newTimestamp);
    }
  };

  const processNext = async () => {
    while (nextToAssign < allThreads.length) {
      const currentIndex = nextToAssign++;
      const thread = allThreads[currentIndex];
      const msg = thread.getMessages()[0];
      const content = `Subject: ${msg.getSubject()}\n\nBody: ${msg.getPlainBody().substring(0, 2000)}`;

      const requestOptions = {
        url: CONFIG.API_URL,
        method: 'post',
        contentType: 'application/json',
        headers: headers,
        payload: JSON.stringify({
          model: CONFIG.MODEL_NAME,
          messages: [
            { role: "system", content: CONFIG.SYSTEM_PROMPT },
            { role: "user", content: content }
          ],
          response_format: { type: "json_object" },
          temperature: 0.1
        }),
        muteHttpExceptions: true
      };

      try {
        const response = UrlFetchApp.fetch(requestOptions.url, requestOptions);
        handleResponse(response, thread, targetLabel);
      } catch (e) {
        console.error(`Request failed for thread ${thread.getId()}: ${e.message}`);
      }

      // Mark this index as done and immediately try to advance checkpoint
      status[currentIndex] = true;
      advanceCheckpoint();
    }
  };

  // Start parallel workers
  const workers = [];
  for (let i = 0; i < Math.min(CONFIG.PARALLEL_LIMIT, allThreads.length); i++) {
    workers.push(processNext());
  }

  await Promise.all(workers);
}

/**
 * Logic to handle individual API responses
 */
function handleResponse(response, thread, targetLabel) {
  if (response.getResponseCode() === 200) {
    try {
      const data = JSON.parse(response.getContentText());
      const classification = JSON.parse(data.choices[0].message.content);
      if (classification.isRecruiter) {
        thread.addLabel(targetLabel);
        console.log(`Labeled [Recruiter]: ${thread.getFirstMessageSubject()}`);
      } else {
        console.log(`Skipped [Not Recruiter]: ${thread.getFirstMessageSubject()}`);
      }
    } catch (err) {
      console.error(`Parsing error for thread ${thread.getId()}: ${err.message}`);
    }
  } else {
    console.error(`Server error ${response.getResponseCode()} for thread ${thread.getId()}: ${response.getContentText()}`);
  }
}

/**
 * Properties Service Helpers
 */
function getLastRunTimestamp() {
  const props = PropertiesService.getScriptProperties();
  const ts = props.getProperty('LAST_RUN_TIMESTAMP');
  return ts ? parseInt(ts, 10) : null;
}

function updateLastRunTimestamp(ts) {
  PropertiesService.getScriptProperties().setProperty('LAST_RUN_TIMESTAMP', ts.toString());
}

/**
 * Sync logic: Populates spreadsheet from the labeled emails
 */
function syncEmailsByLabel() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName('Emails');
  if (!sheet) {
    sheet = spreadsheet.insertSheet('Emails');
    sheet.appendRow(['Thread ID', 'Message ID', 'Date', 'From', 'To', 'Subject', 'Body']);
  }

  const existingMessageIds = getExistingMessageIds(sheet);
  const label = GmailApp.getUserLabelByName(CONFIG.LABEL_NAME); 
  if (!label) return;

  const threads = label.getThreads();
  let messagesData = [];
  
  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const message of messages) {
      const messageId = message.getId();
      if (existingMessageIds.has(messageId)) continue;

      messagesData.push([
        thread.getId(),
        messageId,
        message.getDate(),
        message.getFrom(),
        message.getTo(),
        message.getSubject(),
        message.getPlainBody().substring(0, 1000)
      ]);
    }
  }

  if (messagesData.length > 0) {
    messagesData.sort((a, b) => a[2] - b[2]);
    const startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, messagesData.length, messagesData[0].length).setValues(messagesData);
  }
}

function getExistingMessageIds(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return new Set();
  const messageIds = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
  return new Set(messageIds.flat());
}

function getOrCreateLabel(name) {
  let label = GmailApp.getUserLabelByName(name);
  if (!label) label = GmailApp.createLabel(name);
  return label;
}