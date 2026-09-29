// Small helpers used by every page

// Call the Flask API. Returns the JSON data, or throws an Error with the server's message.
async function api(url, method = "GET", body = null) {
  const options = { method: method, headers: { "Content-Type": "application/json" } };
  if (body) options.body = JSON.stringify(body);
  let response, data;
  try {
    response = await fetch(url, options);
    data = await response.json();
  } catch (e) {
    throw new Error("Cannot reach the server. Please check it is running and try again.");
  }
  if (!response.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

// 1234.5 -> "₹1,234.50"
function money(value) {
  return "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// today's date as YYYY-MM-DD (local time)
function today() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

// show a green / red message under a form
function showMessage(id, text, isError) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = "msg " + (isError ? "error" : "success");
}

// make text safe to put inside HTML
function esc(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : text;
  return div.innerHTML;
}
