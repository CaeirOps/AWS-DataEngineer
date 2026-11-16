// Único ponto de acesso à API do workshop: nenhum outro módulo chama `fetch`.
// Requisições que alteram estado (POST, PUT, DELETE) levam Content-Type JSON,
// o cabeçalho próprio X-Workshop-Request e corpo JSON (`{}` quando vazio).
// GET não envia corpo.

const MUTATING_METHODS = new Set(["POST", "PUT", "DELETE"]);

/** Erro da API com o schema `{error, code, message, http_status}`. */
export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

/** Chamada JSON à API. Lança ApiError com a mensagem original do servidor. */
export async function api(method, url, body) {
  const verb = String(method || "GET").toUpperCase();
  const options = {
    method: verb,
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  };
  if (MUTATING_METHODS.has(verb)) {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-Workshop-Request"] = "1";
    options.body = JSON.stringify(body === undefined || body === null ? {} : body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch (err) {
    throw new ApiError(
      "Não foi possível conectar ao servidor do workshop. Verifique se os containers estão em execução.",
      "NETWORK_ERROR",
      0
    );
  }
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }
  if (!response.ok || (data && data.error === true)) {
    const message =
      (data && data.message) || `Erro ${response.status} ao acessar ${url}.`;
    throw new ApiError(message, data && data.code, response.status);
  }
  return data;
}
