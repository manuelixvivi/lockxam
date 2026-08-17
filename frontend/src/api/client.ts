/**
 * Equigrade v3 — Centralized API Client Layer
 */

export interface AppApiError {
  statusCode: number;
  message: string;
  code?: string;
  details?: Record<string, any>;
}

export interface RequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
  isRetry?: boolean;
}

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private refreshSubscribers: Array<(token: string) => void> = [];

  constructor() {
    this.accessToken = localStorage.getItem("equigrade_access_token");
    this.refreshToken = localStorage.getItem("equigrade_refresh_token");
  }

  public setAccessToken(token: string | null, refreshToken?: string | null): void {
    this.accessToken = token;
    if (token) {
      localStorage.setItem("equigrade_access_token", token);
    } else {
      localStorage.removeItem("equigrade_access_token");
    }

    if (refreshToken !== undefined) {
      this.refreshToken = refreshToken;
      if (refreshToken) {
        localStorage.setItem("equigrade_refresh_token", refreshToken);
      } else {
        localStorage.removeItem("equigrade_refresh_token");
      }
    }
  }

  public getAccessToken(): string | null {
    if (!this.accessToken) {
      this.accessToken = localStorage.getItem("equigrade_access_token");
    }
    return this.accessToken;
  }

  public getRefreshToken(): string | null {
    if (!this.refreshToken) {
      this.refreshToken = localStorage.getItem("equigrade_refresh_token");
    }
    return this.refreshToken;
  }

  public clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem("equigrade_access_token");
    localStorage.removeItem("equigrade_refresh_token");
  }

  private subscribeTokenRefresh(callback: (token: string) => void): void {
    this.refreshSubscribers.push(callback);
  }

  private onTokenRefreshed(newToken: string): void {
    this.refreshSubscribers.forEach((cb) => cb(newToken));
    this.refreshSubscribers = [];
  }

  public async request<T = any>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = endpoint.startsWith("http") ? endpoint : endpoint;
    const { headers: inputHeaders, isRetry, ...restOptions } = options;

    const reqHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      ...(inputHeaders || {}),
    };

    const token = this.getAccessToken();
    if (token && !reqHeaders["Authorization"]) {
      reqHeaders["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...restOptions,
        headers: reqHeaders,
        credentials: "include", // Required for HttpOnly Refresh Cookie
      });

      // Handle HTTP 401 Unauthorized -> Attempt Silent Refresh once
      if (response.status === 401 && !isRetry && !endpoint.includes("/auth/login")) {
        if (!this.isRefreshing) {
          this.isRefreshing = true;
          try {
            const currentRefreshToken = this.getRefreshToken();
            if (!currentRefreshToken) {
              throw new Error("No refresh token available");
            }

            const refreshRes = await this.request<{ access_token: string; refresh_token?: string }>(
              "/api/v1/auth/refresh",
              {
                method: "POST",
                body: JSON.stringify({ refresh_token: currentRefreshToken }),
                isRetry: true,
              }
            );

            const newToken = refreshRes.access_token;
            const newRefreshToken = refreshRes.refresh_token || currentRefreshToken;
            this.setAccessToken(newToken, newRefreshToken);
            this.isRefreshing = false;
            this.onTokenRefreshed(newToken);

            return this.request<T>(endpoint, {
              ...options,
              headers: { ...(inputHeaders || {}), Authorization: `Bearer ${newToken}` },
              isRetry: true,
            });
          } catch (refreshErr) {
            this.isRefreshing = false;
            this.clearTokens();
            window.dispatchEvent(new Event("equigrade:auth_expired"));
            throw refreshErr;
          }
        } else {
          // Wait for active refresh to finish
          return new Promise<T>((resolve, reject) => {
            this.subscribeTokenRefresh(async (newToken: string) => {
              try {
                const res = await this.request<T>(endpoint, {
                  ...options,
                  headers: { ...(inputHeaders || {}), Authorization: `Bearer ${newToken}` },
                  isRetry: true,
                });
                resolve(res);
              } catch (e) {
                reject(e);
              }
            });
          });
        }
      }

      if (!response.ok) {
        let errorData: any = {};
        try {
          errorData = await response.json();
        } catch {
          errorData = { detail: response.statusText };
        }

        let rawDetail = errorData.detail || errorData.message;
        let formattedMsg = "An unexpected error occurred.";

        if (typeof rawDetail === "string") {
          formattedMsg = rawDetail;
        } else if (Array.isArray(rawDetail)) {
          formattedMsg = rawDetail.map((item: any) => item.msg || item.message || JSON.stringify(item)).join(", ");
        } else if (rawDetail && typeof rawDetail === "object") {
          formattedMsg = rawDetail.message || JSON.stringify(rawDetail);
        }

        const normalizedError: AppApiError = {
          statusCode: response.status,
          message: formattedMsg,
          code: errorData.code,
          details: errorData.details,
        };

        throw normalizedError;
      }


      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T;
      }

      return await response.json();
    } catch (err: any) {
      if (err.statusCode) throw err;

      throw {
        statusCode: 0,
        message: err.message || "Network connection failure.",
      } as AppApiError;
    }
  }

  public get<T = any>(endpoint: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, { method: "GET", headers });
  }

  public post<T = any>(endpoint: string, body?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  public put<T = any>(endpoint: string, body?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  public delete<T = any>(endpoint: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE", headers });
  }
}

export const apiClient = new ApiClient();
