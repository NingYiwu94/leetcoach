const BRIDGE_URL = "http://127.0.0.1:18777";
const LOCAL_PUSH_URL = "http://127.0.0.1:8765/leetcode-submissions";
const CACHE_KEY = "leetcode_submission_cache";
const POLL_ALARM = "leetcoach_bridge_poll";
let bridgeBusy = false;


async function runInPage(username, limit) {
  const queries = [
    {
      name: "submissionList",
      url: "https://leetcode.cn/graphql/",
      payload: {
        query: `
          query submissionList(
            $offset: Int!,
            $limit: Int!,
            $lastKey: String,
            $questionSlug: String
          ) {
            submissionList(
              offset: $offset,
              limit: $limit,
              lastKey: $lastKey,
              questionSlug: $questionSlug
            ) {
              submissions {
                title
                titleSlug
                statusDisplay
                lang
                timestamp
              }
            }
          }
        `,
        variables: {
          offset: 0,
          limit,
          lastKey: null,
          questionSlug: ""
        }
      }
    },
    {
      name: "recentACSubmissions",
      url: "https://leetcode.cn/graphql/noj-go/",
      payload: {
        query: `
          query recentAcSubmissions($userSlug: String!) {
            recentACSubmissions(userSlug: $userSlug) {
              submitTime
              question {
                title
                translatedTitle
                titleSlug
              }
            }
          }
        `,
        variables: {userSlug: username}
      }
    }
  ];
  const attempts = [];

  for (const item of queries) {
    const response = await fetch(item.url, {
      method: "POST",
      credentials: "include",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(item.payload)
    });
    const text = await response.text();
    attempts.push({
      name: item.name,
      url: item.url,
      status: response.status,
      text: text.slice(0, 500)
    });

    if (!response.ok) {
      continue;
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch (error) {
      attempts[attempts.length - 1].parse_error = String(error);
      continue;
    }

    const fullList = data?.data?.submissionList?.submissions;
    if (Array.isArray(fullList)) {
      return {
        success: true,
        submissions: fullList.map((submission) => ({
          title: submission.title || "",
          title_slug: submission.titleSlug || "",
          status: submission.statusDisplay || "",
          language: submission.lang || "",
          submit_time: submission.timestamp || "",
          timestamp: submission.timestamp || ""
        })),
        request_url: item.url,
        raw_response_preview: text.slice(0, 500),
        attempts
      };
    }

    const recentAc = data?.data?.recentACSubmissions;
    if (Array.isArray(recentAc)) {
      return {
        success: true,
        submissions: recentAc.map((submission) => ({
          title:
            submission?.question?.translatedTitle ||
            submission?.question?.title ||
            "",
          title_slug: submission?.question?.titleSlug || "",
          status: "Accepted",
          language: "",
          submit_time: submission.submitTime || "",
          timestamp: submission.submitTime || ""
        })),
        request_url: item.url,
        raw_response_preview: text.slice(0, 500),
        attempts
      };
    }
  }

  const lastAttempt = attempts[attempts.length - 1] || {};
  return {
    success: false,
    error_type:
      lastAttempt.status === 401 || lastAttempt.status === 403
        ? "BrowserLoginRequired"
        : "BrowserExtensionError",
    error_message: "浏览器页面未能读取提交记录，请确认当前已登录力扣。",
    request_url: lastAttempt.url || "https://leetcode.cn/",
    raw_response_preview: lastAttempt.text || "",
    attempts
  };
}


async function saveCache(username, result) {
  if (!result?.success || !Array.isArray(result.submissions)) {
    return;
  }

  await chrome.storage.local.set({
    [CACHE_KEY]: {
      username,
      cached_at: new Date().toISOString(),
      submissions: result.submissions,
      request_url: result.request_url || "",
      attempts: result.attempts || []
    }
  });
  pushSubmissionsToLeetCoach(username, result, "cache_refresh");
}


async function pushSubmissionsToLeetCoach(username, result, trigger) {
  if (!result?.success || !Array.isArray(result.submissions)) {
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 1800);
  try {
    await fetch(LOCAL_PUSH_URL, {
      method: "POST",
      cache: "no-store",
      signal: controller.signal,
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        username,
        trigger,
        pushed_at: new Date().toISOString(),
        submissions: result.submissions,
        request_url: result.request_url || "",
        from_extension_cache: Boolean(result.from_cache),
        extension_version: chrome.runtime.getManifest().version
      })
    });
  } catch (error) {
    // LeetCoach may be closed. Local push is best-effort and should stay quiet.
  } finally {
    clearTimeout(timeoutId);
  }
}


async function loadCache(username, limit) {
  const stored = await chrome.storage.local.get(CACHE_KEY);
  const cache = stored?.[CACHE_KEY];
  if (
    !cache ||
    cache.username !== username ||
    !Array.isArray(cache.submissions)
  ) {
    return null;
  }

  return {
    success: true,
    submissions: cache.submissions.slice(0, limit),
    request_url: cache.request_url || "chrome.storage.local",
    raw_response_preview: "",
    attempts: cache.attempts || [],
    from_cache: true,
    cache_time: cache.cached_at || ""
  };
}

function localDateString(value) {
  try {
    const date = value ? new Date(value) : new Date();
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  } catch (error) {
    return "";
  }
}

function isLeetCodeUrl(url) {
  const value = String(url || "").toLowerCase();
  return (
    value.startsWith("https://leetcode.cn/")
    || value.startsWith("http://leetcode.cn/")
  );
}

function isLeetCodeTab(tab) {
  if (!tab || typeof tab !== "object") {
    return false;
  }
  return isLeetCodeUrl(tab.url) || /leetcode/i.test(String(tab.title || ""));
}


async function findLeetCodeTab() {
  const tabs = await chrome.tabs.query({});
  return tabs.find((tab) => isLeetCodeTab(tab) && tab.id) || null;
}


async function listLeetCodeTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.filter((tab) => isLeetCodeTab(tab));
}


async function ensureContentScript(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: {tabId},
      files: ["content.js"]
    });
    return true;
  } catch (error) {
    return false;
  }
}


async function ensureContentScriptOnLeetCodeTabs() {
  const tabs = await listLeetCodeTabs();
  for (const tab of tabs) {
    if (tab?.id) {
      await ensureContentScript(tab.id);
    }
  }
  return tabs.length;
}


async function runInTab(tabId, username, limit) {
  const results = await chrome.scripting.executeScript({
    target: {tabId},
    world: "MAIN",
    func: runInPage,
    args: [username, limit]
  });
  return results?.[0]?.result || null;
}


async function collectSubmissions(username, limit, preferFresh = true) {
  if (preferFresh) {
    const tab = await findLeetCodeTab();
    if (tab?.id) {
      try {
        const freshResult = await runInTab(tab.id, username, limit);
        if (freshResult?.success) {
          await saveCache(username, freshResult);
          return {...freshResult, from_cache: false, cache_time: ""};
        }
      } catch (error) {
        // A cached result is still useful if the page is navigating.
      }
    }
  }

  const cachedResult = await loadCache(username, limit);
  if (cachedResult) {
    return cachedResult;
  }

  return {
    success: false,
    submissions: [],
    error_type: "BrowserCacheUnavailable",
    error_message:
      "尚无可用同步缓存。请在已登录的 Chrome 中打开一次力扣页面，扩展会自动缓存最近提交。",
    request_url: "chrome.storage.local",
    raw_response_preview: "",
    attempts: []
  };
}


async function diagnoseSync(username, limit) {
  const tabs = await listLeetCodeTabs();
  const stored = await chrome.storage.local.get(CACHE_KEY);
  const cache = stored?.[CACHE_KEY] || null;

  let freshResult = null;
  if (tabs.length === 0) {
    freshResult = {
      success: false,
      error_type: "NoLeetCodeTabOpen",
      error_message: "当前 Chrome 中没有打开 leetcode.cn 页面。"
    };
  } else if (tabs[0]?.id) {
    try {
      freshResult = await runInTab(tabs[0].id, username, limit);
      if (freshResult?.success) {
        await saveCache(username, freshResult);
      }
    } catch (error) {
      freshResult = {
        success: false,
        error_type: "ExtensionRuntimeError",
        error_message: String(error)
      };
    }
    if (!freshResult) {
      freshResult = {
        success: false,
        error_type: "NoFetchResult",
        error_message: "扩展未收到页面返回的抓取结果。"
      };
    }
  }

  const cacheTime = cache?.cached_at || "";
  const cacheIsToday = Boolean(cacheTime) && (
    localDateString(cacheTime) === localDateString()
  );
  const submissions = Array.isArray(cache?.submissions)
    ? cache.submissions
    : [];

  return {
    success: true,
    mode: "diagnose",
    extension_version: chrome.runtime.getManifest().version,
    extension_online: true,
    username,
    leetcode_tabs_found: tabs.length,
    total_tabs_seen: (await chrome.tabs.query({})).length,
    detected_tab_urls: tabs
      .filter((tab) => tab?.url)
      .slice(0, 3)
      .map((tab) => tab.url),
    cache_available: Boolean(cache),
    cache_time: cacheTime,
    cache_is_today: cacheIsToday,
    cache_submission_count: submissions.length,
    cache_username: cache?.username || "",
    fresh_fetch_success: Boolean(freshResult?.success),
    fresh_result_count: Array.isArray(freshResult?.submissions)
      ? freshResult.submissions.length
      : 0,
    fresh_error_type: freshResult?.error_type || "",
    fresh_error_message: freshResult?.error_message || "",
    fresh_request_url: freshResult?.request_url || "",
    fresh_preview: freshResult?.raw_response_preview || ""
  };
}


async function postBridgeResult(payload) {
  await fetch(`${BRIDGE_URL}/result`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
}


async function pollBridge() {
  if (bridgeBusy) {
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

    const result = task.mode === "diagnose"
      ? await diagnoseSync(task.username, task.limit)
      : await collectSubmissions(
          task.username,
          task.limit,
          true
        );
    await postBridgeResult({...result, task_id: task.task_id});
  } catch (error) {
    // The local bridge normally does not exist when LeetCoach is closed.
  } finally {
    bridgeBusy = false;
  }
}


async function refreshCacheFromSender(sender, username, limit) {
  if (!sender.tab?.id) {
    return {
      success: false,
      error_type: "MissingLeetCodeTab",
      error_message: "当前消息不是来自力扣页面。"
    };
  }

  let resolvedUsername = username;
  if (!resolvedUsername) {
    const stored = await chrome.storage.local.get(CACHE_KEY);
    resolvedUsername = stored?.[CACHE_KEY]?.username || "";
  }
  if (!resolvedUsername) {
    return {
      success: false,
      error_type: "MissingUsername",
      error_message: "尚未收到 LeetCoach 用户名，暂不刷新缓存。"
    };
  }

  const result = await runInTab(
    sender.tab.id,
    resolvedUsername,
    limit
  );
  if (result?.success) {
    await saveCache(resolvedUsername, result);
  }
  return result;
}


chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "refresh_submission_cache") {
    refreshCacheFromSender(
      sender,
      message.username || "",
      message.limit || 20
    )
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({
        success: false,
        error_type: "ExtensionRuntimeError",
        error_message: String(error)
      }));
    return true;
  }

  if (message?.type === "run_leetcode_sync") {
    const task = message.task || {};
    const action = task.mode === "diagnose"
      ? diagnoseSync(task.username || "", task.limit || 20)
      : collectSubmissions(task.username || "", task.limit || 20, true);
    action
      .then((result) => sendResponse({...result, task_id: task.task_id}))
      .catch((error) => sendResponse({
        task_id: task.task_id,
        success: false,
        error_type: "ExtensionRuntimeError",
        error_message: String(error)
      }));
    return true;
  }

  return false;
});


chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(POLL_ALARM, {periodInMinutes: 0.5});
  ensureContentScriptOnLeetCodeTabs();
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(POLL_ALARM, {periodInMinutes: 0.5});
  ensureContentScriptOnLeetCodeTabs();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (
    changeInfo.status === "complete"
    && isLeetCodeTab(tab)
  ) {
    ensureContentScript(tabId);
  }
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) {
    pollBridge();
  }
});

chrome.alarms.create(POLL_ALARM, {periodInMinutes: 0.5});
ensureContentScriptOnLeetCodeTabs();
pollBridge();
