import {
  apiRequest,
  ApiError,
  hasCsrfToken,
} from "@/lib/api/client";

export type LoginCredentials = {
  username: string;
  password: string;
};

export type RegisterCredentials = {
  username: string;
  email: string;
  password: string;
  registrationKey: string;
};

export type CurrentUser = {
  id: number;
  username: string;
  email: string;
  is_admin: number;
};

export type SiteSettings = {
  login_required: boolean;
};

type CurrentUserResponse = {
  user: CurrentUser;
};

const sessionErrorStatuses = new Set([401, 403, 422]);

function isSessionError(error: unknown) {
  return error instanceof ApiError && sessionErrorStatuses.has(error.status);
}

async function clearSession() {
  await apiRequest("/api/session/clear", {
    method: "POST",
    headers: {
      "X-Session-Reset": "1",
    },
  });
}

export async function login(credentials: LoginCredentials) {
  const formData = new FormData();

  formData.set("username", credentials.username);
  formData.set("password", credentials.password);

  await apiRequest("/api/login", {
    method: "POST",
    body: formData,
  });
}

export async function register(credentials: RegisterCredentials) {
  const formData = new FormData();

  formData.set("username", credentials.username);
  formData.set("email", credentials.email);
  formData.set("password", credentials.password);
  formData.set("registration_key", credentials.registrationKey);

  await apiRequest("/api/register", {
    method: "POST",
    body: formData,
  });
}

export async function refreshSession() {
  try {
    await apiRequest("/api/refresh", {
      method: "POST",
      csrf: "refresh",
    });
  } catch (error) {
    if (isSessionError(error)) {
      await clearSession().catch(() => undefined);
    }

    throw error;
  }
}

// Retries a request once after refreshing an expired access token.
export async function requestWithSessionRefresh<T>(request: () => Promise<T>) {
  try {
    return await request();
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) {
      throw error;
    }

    await refreshSession();
    return request();
  }
}

function requestCurrentUser() {
  return apiRequest<CurrentUserResponse>("/api/user");
}

export async function getCurrentUser() {
  try {
    return await requestCurrentUser();
  } catch (error) {
    if (!isSessionError(error)) {
      throw error;
    }

    await refreshSession();
    return requestCurrentUser();
  }
}

export async function getOptionalCurrentUser() {
  if (!hasCsrfToken("access") && !hasCsrfToken("refresh")) {
    return null;
  }

  try {
    const response = await getCurrentUser();
    return response.user;
  } catch (error) {
    if (isSessionError(error)) {
      return null;
    }

    throw error;
  }
}

export function getSiteSettings() {
  return apiRequest<SiteSettings>("/api/site-settings");
}

function requestLogout() {
  return apiRequest("/api/logout", {
    method: "POST",
    csrf: "access",
  });
}

export async function logout() {
  try {
    await requestLogout();
  } catch (error) {
    if (!isSessionError(error)) {
      throw error;
    }

    try {
      await refreshSession();
      await requestLogout();
    } catch (retryError) {
      if (!isSessionError(retryError)) {
        throw retryError;
      }

      await clearSession().catch(() => undefined);
    }
  }
}
