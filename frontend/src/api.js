// Small fetch wrapper for the Within24 API.
const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "within24:token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable (private mode): the session lasts until the tab closes.
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const FIELD_NAMES = {
  email: "Email",
  password: "Password",
  full_name: "Name",
  name: "Name",
  starts_at: "Start time",
  ends_at: "End time",
  earning_minutes: "Earning time",
};

// Turn one FastAPI/Pydantic validation error into a plain sentence.
function validationMessage({ loc = [], msg = "" }) {
  const field = FIELD_NAMES[loc[loc.length - 1]];
  const text = msg.replace(/^Value error, /, "");
  const minLength = text.match(/at least (\d+) characters?/);
  if (field && minLength) return `${field} must be at least ${minLength[1]} characters.`;
  if (field && /valid email/i.test(text)) return "Enter a valid email address.";
  if (field && /field required/i.test(text)) return `${field} is required.`;
  return text.endsWith(".") ? text : `${text}.`;
}

// FastAPI returns errors as {detail: "..."} or {detail: [{loc, msg}]} for validation.
function errorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) return detail.map(validationMessage).join(" ");
  return status >= 500 ? "Something went wrong on the server. Try again in a minute." : "That request didn't work.";
}

async function request(path, { method = "GET", body, params } = {}) {
  const url = new URL(`${API_URL}${path}`);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });

  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status);
  return data;
}

export const api = {
  register: (email, password, fullName) =>
    request("/auth/register", { method: "POST", body: { email, password, full_name: fullName || null } }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/auth/me"),

  listJobs: () => request("/jobs"),
  createJob: (job) => request("/jobs", { method: "POST", body: job }),
  updateJob: (id, changes) => request(`/jobs/${id}`, { method: "PATCH", body: changes }),
  deleteJob: (id) => request(`/jobs/${id}`, { method: "DELETE" }),

  listShifts: (params) => request("/shifts", { params }),
  createShift: (shift) => request("/shifts", { method: "POST", body: shift }),
  updateShift: (id, shift) => request(`/shifts/${id}`, { method: "PUT", body: shift }),
  deleteShift: (id) => request(`/shifts/${id}`, { method: "DELETE" }),

  listBreaks: () => request("/breaks"),
  createBreak: (schoolBreak) => request("/breaks", { method: "POST", body: schoolBreak }),
  deleteBreak: (id) => request(`/breaks/${id}`, { method: "DELETE" }),

  summary: (date, weeksBack) => request("/summary", { params: { date, weeks_back: weeksBack } }),
  checkShift: (shift) => request("/check-shift", { method: "POST", body: shift }),
  rules: () => request("/rules"),
};
