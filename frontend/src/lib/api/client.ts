type ApiErrorResponse = {
  message?: string;
  msg?: string;
};

export type CsrfTokenType = "access" | "refresh";

export type ApiRequestOptions = RequestInit & {
  csrf?: CsrfTokenType;
};

const CSRF_COOKIE_NAMES: Record<CsrfTokenType, string> = {
  access: "csrf_access_token",
  refresh: "csrf_refresh_token",
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getErrorMessage(data: unknown) {
  if (typeof data !== "object" || data === null) {
    return null;
  }

  const response = data as ApiErrorResponse;

  if (typeof response.message === "string") {
    return response.message;
  }

  return typeof response.msg === "string" ? response.msg : null;
}

function getCookie(name: string) {
  if (typeof document === "undefined") {
    return null;
  }

  const cookiePrefix = `${name}=`;
  const cookie = document.cookie
    .split("; ")
    .find((value) => value.startsWith(cookiePrefix));

  return cookie
    ? decodeURIComponent(cookie.slice(cookiePrefix.length))
    : null;
}

export function hasCsrfToken(type: CsrfTokenType) {
  return getCookie(CSRF_COOKIE_NAMES[type]) !== null;
}

export async function apiResponse(
  path: string,
  options: ApiRequestOptions = {},
): Promise<Response> {
  const { csrf, ...requestOptions } = options;
  const headers = new Headers(requestOptions.headers);

  if (csrf) {
    const csrfToken = getCookie(CSRF_COOKIE_NAMES[csrf]);

    if (!csrfToken) {
      throw new ApiError("Missing CSRF token. Please sign in again.", 403);
    }

    headers.set("X-CSRF-TOKEN", csrfToken);
  }

  let response: Response;

  try {
    response = await fetch(path, {
      ...requestOptions,
      credentials: "same-origin",
      headers,
    });
  } catch {
    throw new ApiError("Unable to reach the server. Please try again.", 0);
  }

  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as unknown;

    throw new ApiError(
      getErrorMessage(data) ?? "The server could not complete the request",
      response.status,
    );
  }

  return response;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const response = await apiResponse(path, options);
  const data = (await response.json().catch(() => null)) as unknown;

  return data as T;
}

// Reads a newline-delimited JSON response, emitting each event as it arrives.
export async function readJsonLines<T>(
  response: Response,
  onEvent: (event: T) => void,
  unreadableMessage: string,
) {
  if (!response.body) {
    throw new ApiError(unreadableMessage, 0);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function emitEvents() {
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim()) {
        onEvent(JSON.parse(line) as T);
      }
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    emitEvents();

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    onEvent(JSON.parse(buffer) as T);
  }
}
