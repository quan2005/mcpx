/**
 * Structured error types for API responses.
 * Enables frontend to handle different error types appropriately.
 */

export const ErrorCodes = {
  SERVER_NOT_FOUND: "SERVER_NOT_FOUND",
  TOOL_NOT_FOUND: "TOOL_NOT_FOUND",
  TOOL_DISABLED: "TOOL_DISABLED",
  RESOURCE_NOT_FOUND: "RESOURCE_NOT_FOUND",
  INVALID_INPUT: "INVALID_INPUT",
  UNAUTHORIZED: "UNAUTHORIZED",
  INTERNAL_ERROR: "INTERNAL_ERROR",
  NETWORK_ERROR: "NETWORK_ERROR",
} as const

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes]

export class ApiError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
    public readonly status: number = 500,
    public readonly details?: unknown
  ) {
    super(message)
    this.name = "ApiError"
  }

  /**
   * Check if error is of a specific type.
   */
  is(code: ErrorCode): boolean {
    return this.code === code
  }

  /**
   * Check if error indicates a not-found condition.
   */
  isNotFound(): boolean {
    return (
      this.code === ErrorCodes.SERVER_NOT_FOUND ||
      this.code === ErrorCodes.TOOL_NOT_FOUND ||
      this.code === ErrorCodes.RESOURCE_NOT_FOUND
    )
  }

  /**
   * Check if error is retryable.
   */
  isRetryable(): boolean {
    return this.code === ErrorCodes.NETWORK_ERROR || this.status >= 500
  }
}

/**
 * Parse API error response into ApiError.
 */
export function parseApiError(response: {
  error?: string
  code?: string
  detail?: unknown
}, status: number): ApiError {
  const code = (response.code as ErrorCode) || inferCodeFromStatus(status)
  return new ApiError(code, response.error || "Unknown error", status, response.detail)
}

function inferCodeFromStatus(status: number): ErrorCode {
  switch (status) {
    case 400:
      return ErrorCodes.INVALID_INPUT
    case 401:
    case 403:
      return ErrorCodes.UNAUTHORIZED
    case 404:
      return ErrorCodes.SERVER_NOT_FOUND
    default:
      return ErrorCodes.INTERNAL_ERROR
  }
}
