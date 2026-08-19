export type ApiErrorKind =
  | 'validation'
  | 'not_found'
  | 'conflict'
  | 'network'
  | 'server'
  | 'invalid_response'

export class ApiClientError extends Error {
  readonly retryableByUser: boolean

  constructor(
    readonly kind: ApiErrorKind,
    retryableByUser: boolean,
  ) {
    super(safeErrorMessage(kind))
    this.name = 'ApiClientError'
    this.retryableByUser = retryableByUser
  }
}

interface JsonRequestOptions<T> {
  method: 'GET' | 'POST'
  body?: object
  headers?: Record<string, string>
  timeoutMs?: number
  validate?: (payload: Record<string, unknown>) => payload is T
}

const defaultTimeoutMs = 90_000

export class HttpClient {
  constructor(private readonly fetchImplementation?: typeof fetch) {}

  async requestJson<T>(path: string, options: JsonRequestOptions<T>): Promise<T> {
    const attempts = options.method === 'GET' ? 2 : 1

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        return await this.requestOnce<T>(path, options)
      } catch (error) {
        if (
          error instanceof ApiClientError &&
          (error.kind === 'network' || error.kind === 'server') &&
          attempt + 1 < attempts
        ) {
          continue
        }
        throw error
      }
    }

    throw new ApiClientError('network', true)
  }

  private async requestOnce<T>(path: string, options: JsonRequestOptions<T>): Promise<T> {
    const controller = new AbortController()
    const timeoutId = globalThis.setTimeout(
      () => controller.abort(),
      options.timeoutMs ?? defaultTimeoutMs,
    )

    let response: Response
    try {
      response = await (this.fetchImplementation ?? globalThis.fetch)(path, {
        method: options.method,
        headers: {
          accept: 'application/json',
          ...(options.body ? { 'content-type': 'application/json' } : {}),
          ...options.headers,
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      })
    } catch {
      throw new ApiClientError('network', true)
    } finally {
      globalThis.clearTimeout(timeoutId)
    }

    if (!response.ok) {
      throw errorForStatus(response.status)
    }

    try {
      const payload: unknown = await response.json()
      if (!isRecord(payload) || (options.validate !== undefined && !options.validate(payload))) {
        throw new ApiClientError('invalid_response', false)
      }
      return payload as T
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError('invalid_response', false)
    }
  }
}

function errorForStatus(status: number): ApiClientError {
  if (status === 422) {
    return new ApiClientError('validation', false)
  }
  if (status === 404) {
    return new ApiClientError('not_found', false)
  }
  if (status === 409) {
    return new ApiClientError('conflict', false)
  }
  return new ApiClientError('server', true)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function safeErrorMessage(kind: ApiErrorKind): string {
  const messages: Record<ApiErrorKind, string> = {
    validation: '提交内容未通过校验，请检查后重试。',
    not_found: '未找到对应的质检任务。',
    conflict: '当前任务状态不支持此操作。',
    network: '网络连接异常或请求超时，请稍后重试。',
    server: '服务暂时不可用，请稍后重试。',
    invalid_response: '服务返回结果异常，请稍后重试。',
  }
  return messages[kind]
}
