// Opens the side panel when the toolbar icon is clicked, in every tab.
// See AI_AGENT_BROWSER_PLAN.md Phase 3 - this is the "lives in Chrome"
// wrapper around the same /agent/api/chat endpoint the /agent/ web page uses.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error('ISP Scraper Agent: failed to set panel behavior', error));
