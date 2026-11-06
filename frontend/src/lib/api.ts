import {
  UserProfileResponse,
  BackendHealthResponse,
  RecommendationsResponse,
  ColdStartQuestionnaire,
  UserSkillProfile,
  IssuePlanResponse,
  GeneratePlanRequest,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function checkBackendHealth(): Promise<BackendHealthResponse> {
  const resp = await fetch(`${API_BASE_URL}/health`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!resp.ok) {
    throw new Error(`Backend health check failed with HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchUserProfile(jwtToken: string): Promise<UserProfileResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/me`, {
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Backend responded with HTTP ${resp.status}`);
  }

  return resp.json();
}

export async function fetchRecommendations(
  jwtToken: string,
  refresh: boolean = false
): Promise<RecommendationsResponse> {
  const url = `${API_BASE_URL}/api/recommendations${refresh ? "?refresh=true" : ""}`;
  const resp = await fetch(url, {
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Backend responded with HTTP ${resp.status}`);
  }

  return resp.json();
}

export async function submitColdStart(
  jwtToken: string,
  answers: ColdStartQuestionnaire
): Promise<UserSkillProfile> {
  const resp = await fetch(`${API_BASE_URL}/api/profile/cold-start`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(answers),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Failed to submit questionnaire: HTTP ${resp.status}`);
  }

  return resp.json();
}

export async function fetchIssuePlan(
  req: GeneratePlanRequest,
  jwtToken?: string | null
): Promise<IssuePlanResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (jwtToken) {
    headers["Authorization"] = `Bearer ${jwtToken}`;
  }

  const resp = await fetch(`${API_BASE_URL}/api/plan`, {
    method: "POST",
    headers,
    body: JSON.stringify(req),
    cache: "no-store",
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Plan generation failed: HTTP ${resp.status}`);
  }

  return resp.json();
}

export async function recordIssueOutcome(
  req: import("./types").RecordOutcomeRequest,
  jwtToken: string
): Promise<{ success: boolean; message: string }> {
  const resp = await fetch(`${API_BASE_URL}/api/outcomes`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(req),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Failed to record outcome: HTTP ${resp.status}`);
  }

  return resp.json();
}

export async function fetchUserOutcomes(
  jwtToken: string,
  limit: number = 50,
  outcomeFilter?: string
): Promise<import("./types").OutcomeRecord[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (outcomeFilter) {
    params.set("outcome", outcomeFilter);
  }
  const resp = await fetch(`${API_BASE_URL}/api/outcomes?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!resp.ok) {
    return [];
  }

  return resp.json();
}

export async function fetchIssueOutcome(
  owner: string,
  repo: string,
  issueNumber: number,
  jwtToken: string
): Promise<import("./types").OutcomeRecord | null> {
  const resp = await fetch(`${API_BASE_URL}/api/outcomes/${owner}/${repo}/${issueNumber}`, {
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (resp.status === 404) {
    return null;
  }
  if (!resp.ok) {
    return null;
  }

  return resp.json();
}

export async function deleteMyData(jwtToken: string): Promise<{ success: boolean; message: string }> {
  const resp = await fetch(`${API_BASE_URL}/api/me/data`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${jwtToken}`,
      Accept: "application/json",
    },
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(errorData.detail || `Failed to delete data: HTTP ${resp.status}`);
  }

  return resp.json();
}
