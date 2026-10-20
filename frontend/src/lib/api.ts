import type { components } from "./api-types";

/** Kiểu schema sinh từ OpenAPI của backend (`just gen-api`). */
export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];

const API_BASE = "/api";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Lỗi theo trường của `422 VALIDATION_ERROR` (api.md mục 1.6). */
  readonly errors: FieldError[];

  constructor(status: number, code: string, detail: string, errors: FieldError[] = []) {
    super(detail);
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  json?: unknown;
  body?: BodyInit;
};

/** Fetch wrapper: gửi cookie phiên, header CSRF cho request thay đổi dữ liệu, parse lỗi `{code, detail}`. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, headers: initHeaders, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();
  const headers = new Headers(initHeaders);
  if (UNSAFE.has(method)) headers.set("X-Requested-With", "fetch");
  let body = rest.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...rest,
      method,
      headers,
      body,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Không kết nối được máy chủ, vui lòng thử lại.");
  }

  if (!res.ok) {
    let code = "INTERNAL";
    let detail = "Đã xảy ra lỗi, vui lòng thử lại.";
    let errors: FieldError[] = [];
    try {
      const data = (await res.json()) as { code?: string; detail?: string; errors?: FieldError[] };
      code = data.code ?? code;
      detail = data.detail ?? detail;
      errors = data.errors ?? errors;
    } catch {
      if (res.status === 413) {
        code = "FILE_TOO_LARGE";
        detail = "File vượt quá 20 MB.";
      }
    }
    throw new ApiError(res.status, code, detail, errors);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return "Đã xảy ra lỗi, vui lòng thử lại.";
}
