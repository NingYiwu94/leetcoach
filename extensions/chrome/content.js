if (!globalThis.__leetcoachSyncContentLoaded__) {
globalThis.__leetcoachSyncContentLoaded__ = true;

const BRIDGE_URL = "http://127.0.0.1:18777";
const CACHE_REFRESH_INTERVAL = 60 * 1000;
const BRIDGE_POLL_INTERVAL = 2 * 1000;
let stopped = false;
let cacheIntervalId = null;
let bridgeIntervalId = null;
let bridgeBusy = false;


function usernameFromPage() {
  const match = window.location.pathname.match(/^\/u\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}


function stopContentWorker() {
  stopped = true;
  if (cacheIntervalId !== null) {
    clearInterval(cacheIntervalId);
    cacheIntervalId = null;
  }
  if (bridgeIntervalId !== null) {
    clearInterval(bridgeIntervalId);
    bridgeIntervalId = null;
  }
}


function isContextInvalidatedError(error) {
  return String(error || "").includes("Extension context invalidated");
}


function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    try {
      if (!chrome?.runtime?.id) {
        stopContentWorker();
        reject(new Error("Extension context invalidated"));
        return;
      }

      chrome.runtime.sendMessage(message, (response) => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          if (isContextInvalidatedError(runtimeError.message)) {
            stopContentWorker();
          }
          reject(new Error(runtimeError.message));
          return;
        }
        resolve(response);
      });
    } catch (error) {
      if (isContextInvalidatedError(error)) {
        stopContentWorker();
      }
      reject(error);
    }
  });
}


async function refreshSubmissionCache() {
  if (stopped) {
    return;
  }

  try {
    await sendRuntimeMessage({
      type: "refresh_submission_cache",
      username: usernameFromPage(),
      limit: 50
    });
  } catch (error) {
    if (!isContextInvalidatedError(error)) {
      console.debug("LeetCoach cache refresh skipped:", error);
    }
  }
}

async function pollLocalBridge() {
  if (stopped || bridgeBusy) {
    return;
  }
  bridgeBusy = true;

  try {
    const response = await fetch(`${BRIDGE_URL}/task`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return;
    }

    const data = await response.json();
    const task = data?.task;
    if (!task) {
      return;
    }

    const result = await sendRuntimeMessage({
      type: "run_leetcode_sync",
      task
    });
    await fetch(`${BRIDGE_URL}/result`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({...result, task_id: task.task_id})
    });
  } catch (error) {
    if (!isContextInvalidatedError(error)) {
      // LeetCoach is normally closed most of the time, so silence bridge misses.
    }
  } finally {
    bridgeBusy = false;
  }
}


cacheIntervalId = setInterval(refreshSubmissionCache, CACHE_REFRESH_INTERVAL);
bridgeIntervalId = setInterval(pollLocalBridge, BRIDGE_POLL_INTERVAL);
refreshSubmissionCache();
pollLocalBridge();
}
